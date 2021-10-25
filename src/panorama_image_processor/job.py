import os
import shutil
from enum import Enum
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from panorama_image_processor.config import get_datastore_config, PANORAMA_RAW_PATH, PANORAMA_INTERMEDIATE_PATH, \
                                            PANORAMA_PROCESSED_PATH, PANORAMA_PROCESSED_CONTAINER, \
                                            PANORAMA_UNPROCESSED_CONTAINER
from panorama_image_processor.datastore.factory import DatastoreFactory
from panorama_image_processor.tasks.blur import BlurPanoramaTask
from panorama_image_processor.tasks.detection import DetectionTask
from panorama_image_processor.transformation.cubic import CubicTransformer
from panorama_image_processor.transformation.equirectangular import EquirectangularTransformer


EQUIRECTANGULAR = 'equirectangular'
CUBIC = 'cubic'


class PanoramaStatus(Enum):
    INITIAL = "initial"
    UNPROCESSED = "unprocessed"
    TRANSFORMED = "transformed"
    DETECTED = "detected"
    BLURRED = "blurred"
    PACKAGED = "packaged"
    DISTRIBUTED = "distributed"
    CLEANEDUP = 'cleanedup'
    DONE = "done"
    FAILED = "failed"


class PanoramaJob(object):

    def __init__(self, path, filename, heading, pitch, roll, source, destination, status=None):
        self.panorama_path = path
        self.panorama_filename = filename

        self.heading = heading
        self.pitch = pitch
        self.roll = roll

        # Get the datastore configuration for the supplied source and destination
        source_datastore_config = get_datastore_config(source)
        destination_datastore_config = get_datastore_config(destination)

        self._source_datastore = DatastoreFactory.get_datastore(source_datastore_config)
        self._destination_datastore = DatastoreFactory.get_datastore(destination_datastore_config)

        self.status = PanoramaStatus.INITIAL if not status else PanoramaStatus(status)
        self.is_running = False

        self._regions = {}

        self.workflow = {
            PanoramaStatus.INITIAL: self._get_raw_panorama,
            PanoramaStatus.UNPROCESSED: self._transform_equirectangular,
            PanoramaStatus.TRANSFORMED: self._detect_regions,
            PanoramaStatus.DETECTED: self._blur_regions,
            PanoramaStatus.BLURRED: self._package_projections,
            PanoramaStatus.PACKAGED: self._distribute,
            PanoramaStatus.DISTRIBUTED: self._cleanup,
            PanoramaStatus.FAILED: self._report_failed,
            PanoramaStatus.CLEANEDUP: self._finish_job,
        }

    @property
    def raw_filename(self):
        return Path(PANORAMA_RAW_PATH) / self.panorama_path / self.panorama_filename

    @property
    def intermediate_filename(self):
        return Path(PANORAMA_INTERMEDIATE_PATH) / self.panorama_path / self.panorama_filename

    @property
    def processed_path(self):
        return Path(PANORAMA_PROCESSED_PATH) / self.panorama_path / Path(self.panorama_filename).with_suffix('')

    @property
    def equirectangular_path(self):
        return self.processed_path / EQUIRECTANGULAR

    @property
    def cubic_path(self):
        return self.processed_path / CUBIC

    def get_equirectangular_filename(self, size):
        return self.equirectangular_path / f'panorama_{size}.jpg'

    def process(self):
        self._is_running = True

        while self._is_running:
            # Determine next action based on PanoramaStatus
            try:
                self.workflow[self.status]()
            except KeyError:
                print(f"No action defined for the current status ({self.status})")
                raise

    def _get_raw_panorama(self):
        print("Get raw panorama")
        self._source_datastore.download_file(self.panorama_path, self.panorama_filename)
        self.status = PanoramaStatus.UNPROCESSED

    def _transform_equirectangular(self):
        print("Transform raw panorama to equirectangular")
        try:
            equirectangular_transformer = EquirectangularTransformer(
                self.raw_filename, self.heading, self.pitch, self.roll)
        except UnidentifiedImageError:
            self.status = PanoramaStatus.FAILED
            return
        projected_panorama = equirectangular_transformer.get_projection()
        # Make sure the directory exists
        Path(self.intermediate_filename).parent.mkdir(parents=True, exist_ok=True)
        projected_panorama.save(self.intermediate_filename)
        self.status = PanoramaStatus.TRANSFORMED

    def _report_failed(self):
        print('Transform raw panorama file failed')
        self._destination_datastore.upload(PANORAMA_UNPROCESSED_CONTAINER, self.processed_path,
                                           destination=self.panorama_path, source_base=PANORAMA_PROCESSED_PATH)
        self.status = PanoramaStatus.CLEANEDUP

    def _detect_regions(self):
        print("Detect regions for faces and license plates")
        detection_task = DetectionTask(self.intermediate_filename)
        self._regions = detection_task.detect_regions()
        self.status = PanoramaStatus.DETECTED

    def _blur_regions(self):
        print("Blur detected regions")
        blur_task = BlurPanoramaTask()
        self._blurred_image = blur_task.get_blurred_image(self.intermediate_filename, self._regions)
        self.status = PanoramaStatus.BLURRED

    def _package_projections(self):
        print("Package panorama in different projections and resolutions")
        self.equirectangular_path.mkdir(parents=True, exist_ok=True)
        self.cubic_path.mkdir(parents=True, exist_ok=True)

        # Store the blurred equirectangular images in multiple resolutions
        self._blurred_image.save(self.get_equirectangular_filename(8000))
        medium_img = self._blurred_image.resize((4000, 2000), Image.ANTIALIAS)
        medium_img.save(self.get_equirectangular_filename(4000))
        small_img = self._blurred_image.resize((2000, 1000), Image.ANTIALIAS)
        small_img.save(self.get_equirectangular_filename(2000))

        cubic_transformer = CubicTransformer(self.get_equirectangular_filename(8000))
        projections = cubic_transformer.get_normalized_projection()
        cubic_transformer.save_as_cubic_file_set(projections, self.cubic_path)
        self.status = PanoramaStatus.PACKAGED

    def _distribute(self):
        print("Distribute package to final destination")
        self._destination_datastore.upload(PANORAMA_PROCESSED_CONTAINER, self.processed_path,
                                           destination=self.panorama_path, source_base=PANORAMA_PROCESSED_PATH)
        self.status = PanoramaStatus.DISTRIBUTED

    def _cleanup(self):
        print("Cleaning up files")
        try:
            os.remove(self.raw_filename)
            os.remove(self.intermediate_filename)
        except os.error:
            pass
        shutil.rmtree(self.processed_path, ignore_errors=True)
        self.status = PanoramaStatus.CLEANEDUP

    def _finish_job(self):
        print("Job finished")
        self.status = PanoramaStatus.DONE
        self._is_running = False
