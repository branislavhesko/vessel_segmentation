from matplotlib import pyplot as plt
import numpy as np
import os
import torch
from tqdm import tqdm
from config import available_models, Configuration, TickColonSegmentation
from loaders.subimage_info_holder import ImageLoader


class Predictor:

    def __init__(self, config: Configuration, cuda: bool = False):
        self._config = config
        self.model = None
        self._cuda = cuda
        self._transform = self._config.VAL_AUGMENTATION
        weights_path = os.path.join(self._config.OUTPUT, self._config.OUTPUT_FOLDER, self._config.CHECKPOINT)
        assert os.path.exists(weights_path)
        self._load_model(weights_path)
        self._image_loader = ImageLoader((self._config.CROP_SIZE, self._config.CROP_SIZE), self._config.STRIDE)

    @torch.no_grad()
    def predict(self, image):
        assert len(image.shape) == 3, "Image should be in RGB format for now."
        self._image_loader.set_image_and_mask(image, image[:, :, 0])
        indices = self._image_loader.get_indices()
        count_map = np.zeros(image.shape[:2]).astype(np.float32)
        prediction = torch.zeros((self._config.NUM_CLASSES, *image.shape[:2]))
        if self._cuda:
            prediction = prediction.cuda()
        for idx in tqdm(indices):
            input_slice = np.copy(image[idx[0]: idx[2], idx[1]: idx[3], :])
            input_slice = self._transform(input_slice, input_slice[:, :, 0])[0]
            if self._cuda:
                input_slice = input_slice.cuda()
            output = self.model(input_slice.unsqueeze(dim=0))
            prediction[:, idx[0]: idx[2], idx[1]: idx[3]] += torch.squeeze(output[0, :, :, :].data)
            count_map[idx[0]: idx[2], idx[1]: idx[3]] += 1.

        prediction = prediction.cpu().numpy() / count_map
        return np.argmax(prediction, axis=0)

    def _load_model(self, weights_path: str):
        self.model = available_models[self._config.MODEL](self._config.NUM_CLASSES)
        if self._cuda:
            self.model = self.model.cuda()
        self.model.load_state_dict(torch.load(weights_path))
        self.model.eval()


if __name__ == "__main__":
    import cv2
    from PIL import Image
    import glob
    images = glob.glob(os.path.join("./data/tick_eval/kl_32_12d_16bit_tiff/*.tif"))
    predictor = Predictor(TickColonSegmentation(), cuda=True)
    for image in images:
        print("Processing image: {}".format(image))
        base_name = os.path.splitext(os.path.basename(image))[0]
        img = np.array(cv2.imread(image, cv2.IMREAD_COLOR)).astype(np.float32)
        img = img / 255.
        mask = predictor.predict(img)
        cv2.imwrite(os.path.join("./data/output/", base_name + ".png"), mask * 255)
