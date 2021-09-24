from panorama_image_processor.utils.image import get_image_as_rgb_array

# specific property of our pano set source images
SOURCE_WIDTH = 8000     # pixels

# general properties of equirectangular projections
NORTH_0_DEGREES = 0     # default/base heading
PANO_FOV = 360          # field of view in degrees
PANO_HORIZON = 0.5      # fraction of image that is below horizon
PANO_ASPECT = 2         # width over height
PANO_HEIGHT = SOURCE_WIDTH / PANO_ASPECT


class BasePanoramaTransformer(object):
    """
    BaseClass for transforming source panorama images
    """

    def __init__(self, image_path):
        self._pano_rgb = get_image_as_rgb_array(image_path)

    def get_projection(self):
        return NotImplemented
