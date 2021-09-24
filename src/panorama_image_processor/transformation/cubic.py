from math import log
from numpy import arange, meshgrid
from pathlib import Path
from PIL import Image

from .base import BasePanoramaTransformer, PANO_HEIGHT, SOURCE_WIDTH
from panorama_image_processor.utils import image as Img
from panorama_image_processor.utils import math as Math
from panorama_image_processor.utils import cube as Cube

TILE_SIZE = 512
PREVIEW_WIDTH = 256


class CubicTransformer(BasePanoramaTransformer):

    def get_projection(self, target_width=Cube.MAX_CUBIC_WIDTH):
        cube_projections = {}

        # project to sides
        for direction in Cube.CUBE_SIDES:
            # get target pixel set of cube side (cartesian, where r =/= 1, but depends on cube form)
            x, y, z = self._get_cube_side(direction, target_width)

            # rotate vectors according to rotation-matrix for pitch and roll
            x1, y1, z1 = Math.rotate_cartesian_vectors((x, y, z), self.rotation_matrix)

            # transform cartesion vectors back to image coordinates in a equirectangular projection
            x2, y2 = Math.cartesian2cylindrical((x1, y1, z1),
                                                source_width=SOURCE_WIDTH,
                                                source_height=PANO_HEIGHT,
                                                r_is_1=False)

            # sample source image with output meshgrid
            cube_projections[direction] = Img.sample_rgb_array_image_as_array((x2, y2), self._pano_rgb)

        return cube_projections

    def get_normalized_projection(self, target_width=Cube.MAX_CUBIC_WIDTH):
        cube_projections = {}
        for direction in Cube.CUBE_SIDES:
            x2, y2 = Math.cartesian2cylindrical(self._get_cube_side(direction, target_width),
                                                source_width=SOURCE_WIDTH,
                                                source_height=PANO_HEIGHT,
                                                r_is_1=False)
            cube_projections[direction] = Img.sample_rgb_array_image_as_array((x2, y2), self._pano_rgb)
        return cube_projections

    def _get_cube_side(self, side, width):
        # create the target pixel sets expressed as coordinates of a cubic projection of given cube-size
        # u, d, f, b, l, r = up, down, front, back, left, right

        x, y, z = (0, 0, 0)
        half_width = width / 2

        if side == Cube.CUBE_FRONT:
            x = half_width
            y, z = meshgrid(arange(-half_width, half_width, 1),
                            arange(half_width, -half_width, -1))
        elif side == Cube.CUBE_BACK:
            x = -half_width
            y, z = meshgrid(arange(half_width, -half_width, -1),
                            arange(half_width, -half_width, -1))
        elif side == Cube.CUBE_LEFT:
            y = -half_width
            x, z = meshgrid(arange(-half_width, half_width, 1),
                            arange(half_width, -half_width, -1))
        elif side == Cube.CUBE_RIGHT:
            y = half_width
            x, z = meshgrid(arange(half_width, -half_width, -1),
                            arange(half_width, -half_width, -1))
        elif side == Cube.CUBE_UP:
            z = half_width
            y, x = meshgrid(arange(-half_width, half_width, 1),
                            arange(-half_width, half_width, 1))
        elif side == Cube.CUBE_DOWN:
            z = -half_width
            y, x = meshgrid(arange(-half_width, half_width, 1),
                            arange(half_width, -half_width, -1))

        return (x, y, z)

    def save_as_cubic_file_set(self, projections, cubic_path, max_width=Cube.MAX_CUBIC_WIDTH):
        """
        Saves a set of cubic projections (the 6 sides of maximum resolution)
        as a Marzipano fileset
        :param projections: dict of 6 projections, keys are the faces of the cube
        :param cubic_path: the base path of the cubic files
        :param max_width: the maximum cubesize
        :return:
        """
        previews = {}
        for side, img_array in projections.items():
            cube_face = Image.fromarray(img_array)
            preview = cube_face.resize((PREVIEW_WIDTH, PREVIEW_WIDTH), Image.ANTIALIAS)
            previews[side] = preview
            for zoomlevel in range(0, 1 + int(log(max_width / TILE_SIZE, 2))):
                zoom_size = 2 ** zoomlevel * TILE_SIZE
                zoomed_img = cube_face.resize((zoom_size, zoom_size), Image.ANTIALIAS)
                for h_idx, h_start in enumerate(range(0, zoom_size, TILE_SIZE)):
                    for v_idx, v_start in enumerate(range(0, zoom_size, TILE_SIZE)):
                        tile = zoomed_img.crop((h_start, v_start, h_start + TILE_SIZE, v_start + TILE_SIZE))
                        tile_path = Path(cubic_path) / f'{zoomlevel + 1}/{side}/{v_idx}'
                        tile_path.mkdir(parents=True, exist_ok=True)
                        tile.save(tile_path / f'{h_idx}.jpg')

        preview_image = Image.new('RGB', (PREVIEW_WIDTH, 6 * PREVIEW_WIDTH))
        for idx, side in enumerate(Cube.CUBE_SIDES):
            preview_image.paste(previews[side], (0, PREVIEW_WIDTH * idx))
        preview_image.save(cubic_path / "preview.jpg")
