from pathlib import Path

from PIL import Image

from panorama_image_processor.transformation.equirectangular import EquirectangularTransformer
from panorama_image_processor.tasks.detection import DetectionTask
from panorama_image_processor.tasks.blur import BlurPanoramaTask
from panorama_image_processor.transformation.cubic import CubicTransformer


def test_transformation(tmpdir):
    heading, pitch, roll = -0.446629825528845,	-0.467467454247501,	359.754573525395
    dir = Path(__file__).parent / Path('data')
    file = dir / Path('pano_0000_000000.jpg')
    e = EquirectangularTransformer(file, heading, pitch, roll)
    projection = e.get_projection()
    ofile = tmpdir.join('intermediate_filename.jpg')
    projection.save(ofile.strpath)
    detection_task = DetectionTask(ofile.strpath)
    regions = detection_task.detect_regions()
    assert regions[ofile.strpath] == [
        ('kentekenplaat', [3958, 2133, 4006, 2146]),
        ('kentekenplaat', [7252, 2119, 7299, 2133])]
    blur_task = BlurPanoramaTask()
    blurred_image = blur_task.get_blurred_image(ofile.strpath,  regions)
    blurred_image.save(ofile.strpath)
    blurred_image.resize((2000, 1000), Image.ANTIALIAS)
    cubic_transformer = CubicTransformer(ofile.strpath)
    projections = cubic_transformer.get_normalized_projection()
    cubic_path = Path(tmpdir.mkdir('cubic'))
    cubic_transformer.save_as_cubic_file_set(projections, cubic_path)