import tensorflow as tf
import numpy as np

import gpflow

from elfi.methods.bo.iwvi.layers import RegularizerType


class DGP_VI(gpflow.models.GPModel):
    def __init__(self, X, Y, layers, likelihood,
                 num_samples=1,
                 minibatch_size=None,
                 name=None):
        gpflow.Parameterized.__init__(self, name=name)

        self.likelihood = likelihood

        self.num_data = X.shape[0]
        self.num_samples = num_samples

        if minibatch_size is None:
            self.X = gpflow.params.DataHolder(X)
            self.Y = gpflow.params.DataHolder(Y)
        else:
            self.X = gpflow.params.Minibatch(X, batch_size=minibatch_size, seed=0)
            self.Y = gpflow.params.Minibatch(Y, batch_size=minibatch_size, seed=0)

        self.layers = gpflow.params.ParamList(layers)

    @gpflow.params_as_tensors
    def propagate(self, X, full_cov=False, inference_amorization_inputs=None, is_sampled_local_regularizer=False):

        samples, means, covs, kls, kl_types = [X, ], [], [], [], []

        for layer in self.layers:
            sample, mean, cov, kl = layer.propagate(samples[-1],
                                                    full_cov=full_cov,
                                                    inference_amorization_inputs=inference_amorization_inputs,
                                                    is_sampled_local_regularizer=is_sampled_local_regularizer)
            samples.append(sample)
            means.append(mean)
            covs.append(cov)
            kls.append(kl)
            kl_types.append(layer.regularizer_type)

        return samples[1:], means, covs, kls, kl_types

    @gpflow.params_as_tensors
    def _build_likelihood(self):
        X_tiled = tf.tile(self.X, [self.num_samples, 1])  # SN, Dx
        Y_tiled = tf.tile(self.Y, [self.num_samples, 1])  # SN, Dy

        XY = tf.concat([X_tiled, Y_tiled], -1)  # SN, Dx+Dy

        # Following Salimbeni 2017, the sampling is independent over N
        # The flag is_sampled_local_regularizer=False means that the KL is returned for the regularizer

        samples, means, covs, kls, kl_types = self.propagate(X_tiled,
                                                             full_cov=False,
                                                             inference_amorization_inputs=XY,
                                                             is_sampled_local_regularizer=False)

        local_kls = [kl for kl, t in zip(kls, kl_types) if t is RegularizerType.LOCAL]
        global_kls = [kl for kl, t in zip(kls, kl_types) if t is RegularizerType.GLOBAL]

        var_exp = self.likelihood.variational_expectations(means[-1], covs[-1], Y_tiled)  # SN, Dy

        # Product over the columns of Y
        L_SN = tf.reduce_sum(var_exp, -1)  # SN, Dy -> SN

        shape_S_N = [self.num_samples, tf.shape(self.X)[0]]
        L_S_N = tf.reshape(L_SN, shape_S_N)

        if len(local_kls) > 0:
            local_kls_SN_D = tf.concat(local_kls, -1)  # SN, sum(W_dims)
            local_kls_SN = tf.reduce_sum(local_kls_SN_D, -1)
            local_kls_S_N = tf.reshape(local_kls_SN, shape_S_N)
            L_S_N -= local_kls_S_N  # SN

        scale = tf.cast(self.num_data, gpflow.settings.float_type)\
                / tf.cast(tf.shape(self.X)[0], gpflow.settings.float_type)

        # This line is replaced with tf.reduce_logsumexp in the IW case
        logp = tf.reduce_mean(L_S_N, 0)

        return tf.reduce_sum(logp) * scale - tf.reduce_sum(global_kls)

    @gpflow.params_as_tensors
    def _build_predict(self, X, full_cov=False):
        fs, means, covs, _, _ = self.propagate(X, full_cov=full_cov)
        return fs[-1], means[-1], covs[-1]

    @gpflow.params_as_tensors
    def _build_predict_decomp(self, X, full_cov=False):
        fs, means, covs, _, _ = self.propagate(X, full_cov=full_cov)
        return fs[-1], means[-1], covs

    @gpflow.params_as_tensors
    @gpflow.autoflow((gpflow.settings.float_type, [None, None]), (gpflow.settings.int_type, ()))
    def predict_f_multisample(self, X, S):
        X_tiled = tf.tile(X[None, :, :], [S, 1, 1])
        _, means, covs, _, _ = self.propagate(X_tiled)
        return means[-1], covs[-1]

    @gpflow.params_as_tensors
    @gpflow.autoflow((gpflow.settings.float_type, [None, None]), (gpflow.settings.int_type, ()))
    def predict_y_samples(self, X, S):
        X_tiled = tf.tile(X[None, :, :], [S, 1, 1])
        _, means, covs, _, _ = self.propagate(X_tiled)
        m, v = self.likelihood.predict_mean_and_var(means[-1], covs[-1])
        z = tf.random_normal(tf.shape(means[-1]), dtype=gpflow.settings.float_type)

        '''res_mean = list()
        res_var = list()
        for i in range(0, len(covs)):
            m1, v1 = self.likelihood.predict_mean_and_var(means[i], covs[i])
            res_mean.append(m1)
            res_var.append(v1)'''
            
        return m + z * v**0.5


class DGP_IWVI(DGP_VI):
    @gpflow.params_as_tensors
    def _build_likelihood(self):
        X_tiled = tf.tile(self.X[:, None, :], [1, self.num_samples, 1])  # N, S, Dx
        Y_tiled = tf.tile(self.Y[:, None, :], [1, self.num_samples, 1])  # N, S, Dy

        XY = tf.concat([X_tiled, Y_tiled], -1)  # N, S, Dx+Dy

        # While the sampling independent over N follows just as in Salimbeni 2017, in this
        # case we need to take full cov samples over the multisample dim S.
        # The flag is_sampled_local_regularizer=True means that the log p/q is returned
        # for the regularizer, rather than the KL
        samples, means, covs, kls, kl_types = self.propagate(X_tiled,
                                                             full_cov=True,  # NB the full_cov is over the S dim
                                                             inference_amorization_inputs=XY,
                                                             is_sampled_local_regularizer=True)

        local_kls = [kl for kl, t in zip(kls, kl_types) if t is RegularizerType.LOCAL]
        global_kls = [kl for kl, t in zip(kls, kl_types) if t is RegularizerType.GLOBAL]

        # This could be made slightly more efficient by making the last layer full_cov=False,
        # but this seems a small price to pay for cleaner code. NB this is only a SxS matrix, not
        # an NxN matrix.
        cov_diag = tf.transpose(tf.matrix_diag_part(covs[-1]), [0, 2, 1])  # N,Dy,K,K -> N,K,Dy
        var_exp = self.likelihood.variational_expectations(means[-1], cov_diag, Y_tiled)  # N, K, Dy


        # Product over the columns of Y
        L_NK = tf.reduce_sum(var_exp, 2)  # N, K, Dy -> N, K

        if len(local_kls) > 0:
            local_kls_NKD = tf.concat(local_kls, -1)  # N, K, sum(W_dims)
            L_NK -= tf.reduce_sum(local_kls_NKD, 2)  # N, K

        scale = tf.cast(self.num_data, gpflow.settings.float_type) \
                / tf.cast(tf.shape(self.X)[0], gpflow.settings.float_type)

        # This is reduce_mean in the VI case.
        logp = tf.reduce_logsumexp(L_NK, 1) - np.log(self.num_samples)

        return tf.reduce_sum(logp) * scale - tf.reduce_sum(global_kls)
