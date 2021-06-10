import os
import sys

import torch
from torch.utils.data import DataLoader

from .base import BaseTask
from panorama_image_processor.config import DETECTION_BASE_PATH
from panorama_image_processor.detection.models.experimental import attempt_load
from panorama_image_processor.detection.utils.datasets import LoadImages
from panorama_image_processor.detection.utils.general import check_img_size, non_max_suppression, scale_coords

DETECTION_MODEL = "models/cto_panorama.pt"
IMAGE_SIZE = 2048
CONFIDENCE_THRESHOLD = 0.3
IOU_THRESHOLD = 0.6


class DetectionTask(BaseTask):

    def __init__(self, panorama_filename):
        # Add detection model path to the sys path, to be able to load the model
        sys.path.append(DETECTION_BASE_PATH)
        self.model = attempt_load(os.path.join(DETECTION_BASE_PATH, DETECTION_MODEL))

        self.device = torch.device("cuda" if torch.cuda.is_available() else 'cpu')
        self.half = self.device.type != 'cpu'  # half precision only supported on CUDA
        stride = int(self.model.stride.max())  # model stride
        self.img_size = check_img_size(IMAGE_SIZE, s=stride)  # check img_size
        if self.half:
            self.model.half()

        self.panorama_filename = panorama_filename

    def detect_regions(self):
        dataset = LoadImages([self.panorama_filename], img_size=self.img_size)
        dataloader = DataLoader(dataset, batch_size=1, shuffle=False)
        names = self.model.module.names if hasattr(self.model, 'module') else self.model.names
        meta_data = {}
        """
        Note that TQDM will show the number of batches to be processed: So if you have 100 images and 
        a batch size of 8, it will do np.ceil(100/8) --> 13 iterations.
        """
        for paths, imgs, im_originals in dataloader:
            imgs = imgs.to(self.device)
            imgs = imgs.half() if self.half else imgs.float()  # uint8 to fp16/32
            imgs /= 255.0  # 0 - 255 to 0.0 - 1.0

            preds = self.model(imgs)[0]
            preds = non_max_suppression(preds, CONFIDENCE_THRESHOLD, IOU_THRESHOLD)

            for idx, det in enumerate(preds):  # detections per image
                path, im0 = paths[idx], im_originals[idx].numpy()
                found_objects = []
                if len(det):
                    # Rescale boxes from img_size to im0 size
                    det[:, :4] = scale_coords(imgs.shape[2:], det[:, :4], im0.shape).round()
                    for *xyxy, conf, cls in reversed(det.numpy()):
                        found_objects.append((names[int(cls)], [int(value) for value in xyxy]))
                meta_data[path] = found_objects

        return meta_data