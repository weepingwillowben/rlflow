import collections
import numpy as np
from .segment_tree import SumSegmentTree, MinSegmentTree
from .base import BaseScheme

class DensitySampleScheme(BaseScheme):
    def __init__(self, max_size, alpha, beta_fn, epsilon=1e-7, seed=None):
        """
        Samples based off density of their weight

        :param max_size: (int) Max number of transitions to store in the buffer. When the buffer overflows the old memories
            are dropped.
        :param max_priority: (float) how much prioritization is used (0 - no prioritization, 1 - full prioritization)
        """
        #assert max_priority > 0

        it_capacity = 1
        while it_capacity < max_size:
            it_capacity *= 2

        self._it_sum = SumSegmentTree(it_capacity)
        self._it_min = MinSegmentTree(it_capacity)
        self.epsilon = epsilon

        self.sample_idxs = np.zeros(max_size, dtype=np.int32)
        self.data_idxs = np.zeros(max_size, dtype=np.int32)
        self.num_idxs = 0
        self.learn_step = 0
        self.alpha = alpha
        self.beta_fn = beta_fn
        self.max_size = max_size
        self.np_random = np.random.RandomState(seed)
        self._max_priority = epsilon

    def add(self, id):
        assert self.num_idxs < self.max_size, "added element makes buffer greater than max size, make sure to remove element first"
        idx = self.num_idxs
        self.data_idxs[idx] = id
        self.sample_idxs[id] = self.num_idxs
        self.num_idxs += 1

        self._it_sum[idx] = self._max_priority
        self._it_min[idx] = self._max_priority

    def sample(self, batch_size):
        if self.num_idxs < batch_size:
            return None, None
        else:
            idxs = self._sample_proportional(batch_size)
            idxs = np.unique(idxs)
            self._it_sum[idxs] = self.epsilon
            while len(idxs) != batch_size:
                add_idxs = self._sample_proportional(batch_size-len(idxs))
                self._it_sum[add_idxs] = self.epsilon
                idxs = np.concatenate([idxs,add_idxs],axis=0)
                idxs = np.unique(idxs)

            beta = self.beta_fn(self.learn_step)
            p_min = self._it_min.min() / self._it_sum.sum()
            max_weight = (p_min * self.num_idxs) ** (-beta)
            p_sample = self._it_sum[idxs] / self._it_sum.sum()
            weights = (p_sample * self.num_idxs) ** (-beta) / max_weight

            ids = self.data_idxs[idxs]
            self.learn_step += 1
            return ids, weights

    def _sample_proportional(self, batch_size):
        total = self._it_sum.sum(0, self.num_idxs)
        mass = self.np_random.random(size=batch_size) * total
        idx = self._it_sum.find_prefixsum_idx(mass)
        return idx

    def remove(self, id):
        idx = int(self.sample_idxs[id])
        new_idx = self.num_idxs-1
        if idx != new_idx:
            new_id = self.data_idxs[new_idx]
            self._it_sum[idx] = self._it_sum[new_idx]
            self._it_min[idx] = self._it_min[new_idx]
            self.data_idxs[idx] = new_id
            self.sample_idxs[new_id] = idx
        self.num_idxs = new_idx

    def update_weights(self, ids, td_errs):
        """
        sets priority of transition at index idxes[i] in buffer
        to priorities[i].

        :param idxes: ([int]) List of idxes of sampled transitions
        :param weights: ([float]) List of updated priorities corresponding to transitions at the sampled idxes
            denoted by variable `idxes`.
        """
        weights = td_errs**self.alpha
        assert len(ids) == len(weights)
        # assert np.min(weights) > 0
        # assert 0 <= np.min(ids) < self.max_size
        idxes = self.sample_idxs[ids]
        new_val = self.epsilon + weights
        self._it_sum[idxes] = new_val
        self._it_min[idxes] = new_val
        self._max_priority = max(np.max(weights), 0.999*self._max_priority)
