from attrbench.lib.masking import Masker
import numpy as np



class ImageMasker(Masker):
    def __init__(self, samples: np.ndarray, attributions: np.ndarray, feature_level, segmented_samples: np.ndarray =None):
        if feature_level not in ("channel", "pixel"):
            raise ValueError(f"feature_level must be 'channel' or 'pixel'. Found {feature_level}.")
        self.feature_level = feature_level
        if not self._check_attribution_shape(samples,attributions):
            raise ValueError(f"samples and attribution shape not compatible for feature level {feature_level}."
                             f"Found shapes {samples.shape} and {attributions.shape}")
        super().__init__(samples, attributions)

        self.segm_samples=segmented_samples
        self.use_segments = self.segm_samples is not None
        if self.segm_samples is not None:
            self.sorted_indices = self.segment_attributions(self.segm_samples, self.attributions).argsort()
            assert(self.sorted_indices.shape[1]-1 == segmented_samples.max())
        else:
            self.sorted_indices = attributions.reshape(attributions.shape[0], -1).argsort()


    def segment_attributions(self,seg_images: np.ndarray, attrs: np.ndarray) -> np.ndarray:
        segments = np.unique(seg_images)
        seg_img_flat = seg_images.reshape(seg_images.shape[0], -1)
        attrs_flat = attrs.reshape(attrs.shape[0], -1)
        avg_attrs = np.zeros((seg_images.shape[0], len(segments)))
        for i, seg in enumerate(segments):  # Segments should be 0, ..., n, but we use enumerate just in case
            mask = (seg_img_flat == seg).astype(np.long)
            masked_attrs = mask * attrs_flat
            mask_size = np.sum(mask, axis=1)
            sum_attrs = np.sum(masked_attrs, axis=1)
            mean_attrs = np.divide(sum_attrs, mask_size, out=np.zeros_like(sum_attrs), where=mask_size!=0)
            # If seg does not exist for image, mean_attrs will be nan. Replace with -inf.
            avg_attrs[:, i] = np.nan_to_num(mean_attrs, nan=-np.inf)
        return avg_attrs

    def get_total_features(self):
        if self.use_segments:
            return self.sorted_indices.shape[1]
        return self.sorted_indices.shape[1]

    def _check_attribution_shape(self, samples, attributions):
        if self.feature_level == "channel":
            # Attributions should be same shape as samples
            return list(samples.shape) == list(attributions.shape)
        elif self.feature_level == "pixel":
            # attributions should have the same shape as samples,
            # except the channel dimension must be 1
            aggregated_shape = list(samples.shape)
            aggregated_shape[1] = 1
            return aggregated_shape == list(attributions.shape)

    def mask_rand(self,k,return_indices=False):
        if k==0:
            return self.samples
        rng = np.random.default_rng()
        if not self.use_segments:
            return super().mask_rand(k, return_indices)
        else:
            # this is done a little different form super(),
            # no shuffle here: for each image, only select segments that exsist in that image
            # k can be large -> rng.choice raises exception if k > number of segments
            indices = np.stack([rng.choice(np.unique(self.segm_samples[i, ...]), size=k, replace=False)
                                for i in range(self.segm_samples.shape[0])])
            masked_samples= self._mask_segments(self.samples, self.segm_samples, indices)
        if return_indices: return masked_samples, indices
        return masked_samples

    def _mask(self, samples: np.ndarray, indices: np.ndarray):
        if self.baseline is None:
            raise ValueError("Masker was not initialized.")
        if self.use_segments:
            return self._mask_segments(self.samples, self.segm_samples, indices)
        else:
            batch_size, num_channels, rows, cols = samples.shape
            num_indices = indices.shape[1]
            batch_dim = np.tile(range(batch_size), (num_indices, 1)).transpose()

            #to_mask = torch.zeros(samples.shape).flatten(1 if self.feature_level == "channel" else 2)
            to_mask = np.zeros(samples.shape)
            if self.feature_level == "channel":
                to_mask = to_mask.reshape((to_mask.shape[0], -1))
            else:
                to_mask = to_mask.reshape((to_mask.shape[0], to_mask.shape[1], -1))
            if self.feature_level == "channel":
                to_mask[batch_dim, indices] = 1.
            else:
                try:
                    to_mask[batch_dim, :, indices] = 1.
                except IndexError:
                    raise ValueError("Masking index was out of bounds. "
                                     "Make sure the masking policy is compatible with method output.")
            to_mask = to_mask.reshape(samples.shape)
            return self._mask_boolean(samples, to_mask)

    def _mask_segments(self, images: np.ndarray, seg_images: np.ndarray, segments: np.ndarray) -> np.ndarray:
        if not (images.shape[0] == seg_images.shape[0] and images.shape[0] == segments.shape[0] and
                images.shape[-2:] == seg_images.shape[-2:]):
            raise ValueError(f"Incompatible shapes: {images.shape}, {seg_images.shape}, {segments.shape}")
        bool_masks = []
        for i in range(images.shape[0]):
            seg_img = seg_images[i, ...]
            segs = segments[i, ...]
            bool_masks.append(np.isin(seg_img, segs))
        bool_masks = np.stack(bool_masks, axis=0)
        return self._mask_boolean(images, bool_masks)

    def _mask_boolean(self, samples, bool_mask):
        bool_mask = bool_mask
        return samples - (bool_mask * samples) + (bool_mask * self.baseline)
    # why not return samples[bool_mask] = self.baseline[bool_mask] ?


    def initialize_baselines(self, samples):
        raise NotImplementedError

