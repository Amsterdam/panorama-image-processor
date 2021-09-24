import cv2
import numpy as np
from scipy import misc
from PIL import Image

from .base import BaseTask, TaskStatus


class BlurPanoramaTask(BaseTask):

    def run(self):
        self._state = TaskStatus.RUNNING
        print("Transform task is running")

    def get_blurred_image(self, intermediate_panorama_filename, meta_data):
        """
        Get the blurred image of a panoramas
        :param intermediate_panorama_filename: The path to the intermediate panorama on the local system
        :param regions: Regions to blur
        :return: PIL image of the panorama with blurred regions
        """
        intermediate_image = Image.open(intermediate_panorama_filename)
        blurred_array = np.asarray(intermediate_image).copy()

        # blur regions
        for image_name, regions in meta_data.items():
            for detected_type, coords in regions:
                left, top, right, bottom = coords
                snippet = blurred_array[top:bottom, left:right]
                blur_kernel_size = 2 * int((bottom - top) / 4) + 1
                snippet = cv2.GaussianBlur(snippet, (blur_kernel_size, blur_kernel_size), blur_kernel_size)
                blurred_array[top:bottom, left:right] = snippet

        blurred_image = Image.fromarray(blurred_array)

        return blurred_image

    def get_unblurred_image(self):
        return misc.fromimage(self.panorama_img)
