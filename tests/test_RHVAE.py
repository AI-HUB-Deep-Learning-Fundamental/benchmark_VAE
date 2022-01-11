import os
from copy import deepcopy

import dill
import pytest
import torch
from torch.optim import SGD, Adadelta, Adagrad, Adam, RMSprop

from pythae.customexception import BadInheritanceError
from pythae.models.base.base_utils import ModelOutput
from pythae.models import RHVAE, RHVAEConfig
from pythae.trainers import BaseTrainer, BaseTrainingConfig
from pythae.pipelines import TrainingPipeline
from pythae.models.nn.default_architectures import (
    Decoder_AE_MLP,
    Encoder_VAE_MLP,
    Metric_MLP,
)
from pythae.models.rhvae.rhvae_config import RHVAEConfig
from tests.data.custom_architectures import (
    Decoder_AE_Conv,
    Encoder_VAE_Conv,
    Metric_MLP_Custom,
    NetBadInheritance,
)

PATH = os.path.dirname(os.path.abspath(__file__))

device = 'cuda' if torch.cuda.is_available() else 'cpu'


@pytest.fixture(params=[RHVAEConfig(), RHVAEConfig(latent_dim=5)])
def model_configs_no_input_dim(request):
    return request.param


@pytest.fixture(
    params=[
        RHVAEConfig(input_dim=(1, 28, 28), latent_dim=1, n_lf=1, reconstruction_loss="bce"),
        RHVAEConfig(input_dim=(1, 2, 18), latent_dim=2, n_lf=1)
    ]
)
def model_configs(request):
    return request.param


@pytest.fixture
def custom_encoder(model_configs):
    return Encoder_VAE_Conv(model_configs)


@pytest.fixture
def custom_decoder(model_configs):
    return Decoder_AE_Conv(model_configs)


@pytest.fixture
def custom_metric(model_configs):
    return Metric_MLP_Custom(model_configs)


class Test_Model_Building:
    @pytest.fixture()
    def bad_net(self):
        return NetBadInheritance()

    def test_build_model(self, model_configs):
        rhvae = RHVAE(model_configs)

        assert all(
            [
                rhvae.n_lf == model_configs.n_lf,
                rhvae.temperature == model_configs.temperature,
            ]
        )

    def test_raises_bad_inheritance(self, model_configs, bad_net):
        with pytest.raises(BadInheritanceError):
            rhvae = RHVAE(model_configs, encoder=bad_net)

        with pytest.raises(BadInheritanceError):
            rhvae = RHVAE(model_configs, decoder=bad_net)

        with pytest.raises(BadInheritanceError):
            rhvae = RHVAE(model_configs, metric=bad_net)

    def test_raises_no_input_dim(
        self, model_configs_no_input_dim, custom_encoder, custom_decoder, custom_metric
    ):
        with pytest.raises(AttributeError):
            rhvae = RHVAE(model_configs_no_input_dim)

        with pytest.raises(AttributeError):
            rhvae = RHVAE(model_configs_no_input_dim, encoder=custom_encoder)

        with pytest.raises(AttributeError):
            rhvae = RHVAE(model_configs_no_input_dim, decoder=custom_decoder)

        with pytest.raises(AttributeError):
            rhvae = RHVAE(model_configs_no_input_dim, metric=custom_metric)

        rhvae = RHVAE(
            model_configs_no_input_dim,
            encoder=custom_encoder,
            decoder=custom_decoder,
            metric=custom_metric,
        )

    def test_build_custom_arch(
        self, model_configs, custom_encoder, custom_decoder, custom_metric
    ):

        rhvae = RHVAE(model_configs, encoder=custom_encoder, decoder=custom_decoder)

        assert rhvae.encoder == custom_encoder
        assert not rhvae.model_config.uses_default_encoder

        assert rhvae.decoder == custom_decoder
        assert not rhvae.model_config.uses_default_encoder

        assert rhvae.model_config.uses_default_metric

        rhvae = RHVAE(model_configs, metric=custom_metric)

        assert rhvae.model_config.uses_default_encoder
        assert rhvae.model_config.uses_default_encoder

        assert rhvae.metric == custom_metric
        assert not rhvae.model_config.uses_default_metric


class Test_Model_Saving:
    def test_default_model_saving(self, tmpdir, model_configs):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = RHVAE(model_configs)

        # set random M_tens and centroids from testing
        model.M_tens = torch.randn(3, 10, 10)
        model.centroids_tens = torch.randn(3, 10, 10)

        model.state_dict()["encoder.layers.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(["model_config.json", "model.pt"])

        # reload model
        model_rec = RHVAE.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens, model.M_tens)
        assert torch.equal(model_rec.centroids_tens, model.centroids_tens)

        assert callable(model_rec.G)
        assert callable(model_rec.G_inv)

    def test_custom_encoder_model_saving(self, tmpdir, model_configs, custom_encoder):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = RHVAE(model_configs, encoder=custom_encoder)

        model.state_dict()["encoder.layers.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(
            ["model_config.json", "model.pt", "encoder.pkl"]
        )

        # reload model
        model_rec = RHVAE.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens, model.M_tens)
        assert torch.equal(model_rec.centroids_tens, model.centroids_tens)

        assert callable(model_rec.G)
        assert callable(model_rec.G_inv)

    def test_custom_decoder_model_saving(self, tmpdir, model_configs, custom_decoder):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = RHVAE(model_configs, decoder=custom_decoder)

        model.state_dict()["encoder.layers.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(
            ["model_config.json", "model.pt", "decoder.pkl"]
        )

        # reload model
        model_rec = RHVAE.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens, model.M_tens)
        assert torch.equal(model_rec.centroids_tens, model.centroids_tens)

        assert callable(model_rec.G)
        assert callable(model_rec.G_inv)

    def test_custom_metric_model_saving(self, tmpdir, model_configs, custom_metric):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = RHVAE(model_configs, metric=custom_metric)

        model.state_dict()["encoder.layers.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(
            ["model_config.json", "model.pt", "metric.pkl"]
        )

        # reload model
        model_rec = RHVAE.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens, model.M_tens)
        assert torch.equal(model_rec.centroids_tens, model.centroids_tens)

        assert callable(model_rec.G)
        assert callable(model_rec.G_inv)

    def test_full_custom_model_saving(
        self, tmpdir, model_configs, custom_encoder, custom_decoder, custom_metric
    ):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = RHVAE(
            model_configs,
            encoder=custom_encoder,
            decoder=custom_decoder,
            metric=custom_metric,
        )

        model.state_dict()["encoder.layers.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(
            [
                "model_config.json",
                "model.pt",
                "encoder.pkl",
                "decoder.pkl",
                "metric.pkl",
            ]
        )

        # reload model
        model_rec = RHVAE.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens, model.M_tens)
        assert torch.equal(model_rec.centroids_tens, model.centroids_tens)

        assert callable(model_rec.G)
        assert callable(model_rec.G_inv)

        model_rec.to(device)

        z = torch.randn(2, model_configs.latent_dim).to(device)

        assert model_rec.G(z).shape == (2, model_configs.latent_dim, model_configs.latent_dim)
        assert model_rec.G_inv(z).shape == (2, model_configs.latent_dim, model_configs.latent_dim)

    def test_raises_missing_files(
        self, tmpdir, model_configs, custom_encoder, custom_decoder, custom_metric
    ):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = RHVAE(
            model_configs,
            encoder=custom_encoder,
            decoder=custom_decoder,
            metric=custom_metric,
        )

        model.state_dict()["encoder.layers.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        os.remove(os.path.join(dir_path, "metric.pkl"))

        # check raises decoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = RHVAE.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "decoder.pkl"))

        # check raises decoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = RHVAE.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "encoder.pkl"))

        # check raises encoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = RHVAE.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "model.pt"))

        # check raises encoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = RHVAE.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "model_config.json"))

        # check raises encoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = RHVAE.load_from_folder(dir_path)


class Test_Model_forward:
    @pytest.fixture
    def demo_data(self):
        data = torch.load(os.path.join(PATH, "data/mnist_clean_train_dataset_sample"))[
            :
        ]
        return (
            data
        )  # This is an extract of 3 data from MNIST (unnormalized) used to test custom architecture

    @pytest.fixture
    def rhvae(self, model_configs, demo_data):
        model_configs.input_dim = tuple(demo_data["data"][0].shape)
        return RHVAE(model_configs)

    def test_model_train_output(self, rhvae, demo_data):

        # model_configs.input_dim = demo_data['data'][0].shape[-1]

        # rhvae = RHVAE(model_configs)

        rhvae.train()

        out = rhvae(demo_data)
        assert set(
            [
                "loss",
                "recon_x",
                "z",
                "z0",
                "rho",
                "eps0",
                "gamma",
                "mu",
                "log_var",
                "G_inv",
                "G_log_det",
            ]
        ) == set(out.keys())

        rhvae.update()

    def test_model_output(self, rhvae, demo_data):

        # model_configs.input_dim = demo_data['data'][0].shape[-1]

        rhvae.eval()

        out = rhvae(demo_data)
        assert set(
            [
                "loss",
                "recon_x",
                "z",
                "z0",
                "rho",
                "eps0",
                "gamma",
                "mu",
                "log_var",
                "G_inv",
                "G_log_det",
            ]
        ) == set(out.keys())

        assert out.z.shape[0] == demo_data["data"].shape[0]
        assert out.recon_x.shape == demo_data["data"].shape


@pytest.mark.slow
class Test_RHVAE_Training:
    @pytest.fixture
    def train_dataset(self):
        return torch.load(os.path.join(PATH, "data/mnist_clean_train_dataset_sample"))

    @pytest.fixture(
        params=[BaseTrainingConfig(num_epochs=3, steps_saving=2, learning_rate=1e-5)]
    )
    def training_configs(self, tmpdir, request):
        tmpdir.mkdir("dummy_folder")
        dir_path = os.path.join(tmpdir, "dummy_folder")
        request.param.output_dir = dir_path
        return request.param

    @pytest.fixture(
        params=[
            torch.rand(1),
            torch.rand(1),
            torch.rand(1)
        ]
    )
    def rhvae(
        self, model_configs, custom_encoder, custom_decoder, custom_metric, request
    ):
        # randomized

        alpha = request.param

        if alpha < 0.125:
            model = RHVAE(model_configs)

        elif 0.125 <= alpha < 0.25:
            model = RHVAE(model_configs, encoder=custom_encoder)

        elif 0.25 <= alpha < 0.375:
            model = RHVAE(model_configs, decoder=custom_decoder)

        elif 0.375 <= alpha < 0.5:
            model = RHVAE(model_configs, metric=custom_metric)

        elif 0.5 <= alpha < 0.625:
            model = RHVAE(model_configs, encoder=custom_encoder, decoder=custom_decoder)

        elif 0.625 <= alpha < 0:
            model = RHVAE(model_configs, encoder=custom_encoder, metric=custom_metric)

        elif 0.750 <= alpha < 0.875:
            model = RHVAE(model_configs, decoder=custom_decoder, metric=custom_metric)

        else:
            model = RHVAE(
                model_configs,
                encoder=custom_encoder,
                decoder=custom_decoder,
                metric=custom_metric,
            )

        return model

    @pytest.fixture(params=[Adam])
    def optimizers(self, request, rhvae, training_configs):
        if request.param is not None:
            optimizer = request.param(
                rhvae.parameters(), lr=training_configs.learning_rate
            )

        else:
            optimizer = None

        return optimizer

    def test_rhvae_train_step(self, rhvae, train_dataset, training_configs, optimizers):
        trainer = BaseTrainer(
            model=rhvae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        step_1_loss = trainer.train_step(epoch=1)

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert not all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_rhvae_eval_step(self, rhvae, train_dataset, training_configs, optimizers):
        trainer = BaseTrainer(
            model=rhvae,
            train_dataset=train_dataset,
            eval_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        step_1_loss = trainer.eval_step(epoch=1)

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_rhvae_main_train_loop(
        self, tmpdir, rhvae, train_dataset, training_configs, optimizers
    ):

        trainer = BaseTrainer(
            model=rhvae,
            train_dataset=train_dataset,
            eval_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        trainer.train()

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert not all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_checkpoint_saving(
        self, tmpdir, rhvae, train_dataset, training_configs, optimizers
    ):

        dir_path = training_configs.output_dir

        trainer = BaseTrainer(
            model=rhvae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        # Make a training step
        step_1_loss = trainer.train_step(epoch=1)

        model = deepcopy(trainer.model)
        optimizer = deepcopy(trainer.optimizer)

        trainer.save_checkpoint(dir_path=dir_path, epoch=0, model=model)

        checkpoint_dir = os.path.join(dir_path, "checkpoint_epoch_0")

        assert os.path.isdir(checkpoint_dir)

        files_list = os.listdir(checkpoint_dir)

        assert set(["model.pt", "optimizer.pt", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not rhvae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not rhvae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        # check pickled custom metric
        if not rhvae.model_config.uses_default_metric:
            assert "metric.pkl" in files_list

        else:
            assert not "metric.pkl" in files_list

        model_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "model.pt"))[
            "model_state_dict"
        ]

        model_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "model.pt"))[
            "model_state_dict"
        ]

        assert all(
            [
                torch.equal(
                    model_rec_state_dict[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        # check reload full model
        model_rec = RHVAE.load_from_folder(os.path.join(checkpoint_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens.cpu(), model.M_tens.cpu())
        assert torch.equal(model_rec.centroids_tens.cpu(), model.centroids_tens.cpu())
        assert type(model_rec.encoder.cpu()) == type(model.encoder.cpu())
        assert type(model_rec.decoder.cpu()) == type(model.decoder.cpu())
        assert type(model_rec.metric.cpu()) == type(model.metric.cpu())

        optim_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "optimizer.pt"))

        assert all(
            [
                dict_rec == dict_optimizer
                for (dict_rec, dict_optimizer) in zip(
                    optim_rec_state_dict["param_groups"],
                    optimizer.state_dict()["param_groups"],
                )
            ]
        )

        assert all(
            [
                dict_rec == dict_optimizer
                for (dict_rec, dict_optimizer) in zip(
                    optim_rec_state_dict["state"], optimizer.state_dict()["state"]
                )
            ]
        )

    def test_checkpoint_saving_during_training(
        self, tmpdir, rhvae, train_dataset, training_configs, optimizers
    ):
        #
        target_saving_epoch = training_configs.steps_saving

        dir_path = training_configs.output_dir

        trainer = BaseTrainer(
            model=rhvae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        model = deepcopy(trainer.model)

        trainer.train()

        training_dir = os.path.join(
            dir_path, f"RHVAE_training_{trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        checkpoint_dir = os.path.join(
            training_dir, f"checkpoint_epoch_{target_saving_epoch}"
        )

        assert os.path.isdir(checkpoint_dir)

        files_list = os.listdir(checkpoint_dir)

        # check files
        assert set(["model.pt", "optimizer.pt", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not rhvae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not rhvae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        # check pickled custom metric
        if not rhvae.model_config.uses_default_metric:
            assert "metric.pkl" in files_list

        else:
            assert not "metric.pkl" in files_list

        model_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "model.pt"))[
            "model_state_dict"
        ]

        assert not all(
            [
                torch.equal(model_rec_state_dict[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_final_model_saving(
        self, tmpdir, rhvae, train_dataset, training_configs, optimizers
    ):

        dir_path = training_configs.output_dir

        trainer = BaseTrainer(
            model=rhvae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        trainer.train()

        model = deepcopy(trainer._best_model)

        training_dir = os.path.join(
            dir_path, f"RHVAE_training_{trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        final_dir = os.path.join(training_dir, f"final_model")
        assert os.path.isdir(final_dir)

        files_list = os.listdir(final_dir)

        assert set(["model.pt", "model_config.json", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not rhvae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not rhvae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        # check pickled custom metric
        if not rhvae.model_config.uses_default_metric:
            assert "metric.pkl" in files_list

        else:
            assert not "metric.pkl" in files_list

        # check reload full model
        model_rec = RHVAE.load_from_folder(os.path.join(final_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens.cpu(), model.M_tens.cpu())
        assert torch.equal(model_rec.centroids_tens.cpu(), model.centroids_tens.cpu())
        assert type(model_rec.encoder.cpu()) == type(model.encoder.cpu())
        assert type(model_rec.decoder.cpu()) == type(model.decoder.cpu())
        assert type(model_rec.metric.cpu()) == type(model.metric.cpu())

    def test_rhvae_training_pipeline(
        self, tmpdir, rhvae, train_dataset, training_configs
    ):

        dir_path = training_configs.output_dir

        # build pipeline
        pipeline = TrainingPipeline(
            model=rhvae, training_config=training_configs
        )

        assert pipeline.training_config.__dict__ == training_configs.__dict__

        # Launch Pipeline
        pipeline(
            train_data=train_dataset.data,  # gives tensor to pipeline
            eval_data=train_dataset.data,  # gives tensor to pipeline
        )

        model = deepcopy(pipeline.trainer._best_model)

        training_dir = os.path.join(
            dir_path, f"RHVAE_training_{pipeline.trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        final_dir = os.path.join(training_dir, f"final_model")
        assert os.path.isdir(final_dir)

        files_list = os.listdir(final_dir)

        assert set(["model.pt", "model_config.json", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not rhvae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not rhvae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        # check pickled custom metric
        if not rhvae.model_config.uses_default_metric:
            assert "metric.pkl" in files_list

        else:
            assert not "metric.pkl" in files_list

        # check reload full model
        model_rec = RHVAE.load_from_folder(os.path.join(final_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        assert torch.equal(model_rec.M_tens.cpu(), model.M_tens.cpu())
        assert torch.equal(model_rec.centroids_tens.cpu(), model.centroids_tens.cpu())
        assert type(model_rec.encoder.cpu()) == type(model.encoder.cpu())
        assert type(model_rec.decoder.cpu()) == type(model.decoder.cpu())
        assert type(model_rec.metric.cpu()) == type(model.metric.cpu())
