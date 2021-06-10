from threading import Thread

from panorama_image_processor.job import PanoramaJob
from panorama_image_processor.queues.base import EmptyQueueException


class PanoramaWorker(Thread):

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue
        self.job = None
        self.message = None

    def run(self):
        print("Worker started")
        while True:
            try:
                # Get the next job from the panorama-processing-queue
                message, job_info = self.queue.dequeue()
            except EmptyQueueException:
                break

            # Create the panorama job and store the current message
            self.job = PanoramaJob(**job_info)
            self.message = message

            self.job.process()

            self.finish()

    def finish(self):
        # Remove message from queue
        print(f"Job finished, removing {self.message.id}")
        self.queue.delete_message(self.message)

    '''
    def process_job(self):
        # First download the raw image from the storage location
        print("download raw file")
        datastore = AzureStorageDatastore()
        datastore.download_file(self.panorama_path, self.panorama_filename)

        print("transform raw panorama")
        equirectangular_transformer = EquirectangularTransformer(self.panorama_path, self.panorama_filename,
                                                                 self.heading, self.pitch, self.roll)
        projected_panorama = equirectangular_transformer.get_projection()
        # Make sure the directory exists
        Path(self.intermediate_filename).parent.mkdir(parents=True, exist_ok=True)
        projected_panorama.save(self.intermediate_filename)

        print("detect regions")
        detection_task = DetectionTask(self.intermediate_filename)
        regions = detection_task.detect_regions()

        print("blur regions")
        blur_task = BlurPanoramaTask()
        blurred_image = blur_task.get_blurred_image(self.intermediate_filename, regions)

        print("create all image formats")
        # Store the blurred images in multiple resolutions and projections in a folder based on the panorama filename
        self.equirectangular_path.mkdir(parents=True, exist_ok=True)
        self.cubic_path.mkdir(parents=True, exist_ok=True)

        blurred_image.save(self.get_equirectangular_filename(8000))
        medium_img = blurred_image.resize((4000, 2000), Image.ANTIALIAS)
        medium_img.save(self.get_equirectangular_filename(4000))
        small_img = blurred_image.resize((2000, 1000), Image.ANTIALIAS)
        small_img.save(self.get_equirectangular_filename(2000))

        blurred_image_array = np.asarray(blurred_image)
        cubic_transformer = CubicTransformer(None, 0, 0, 0,
                                             pano_rgb=get_rgb_channels_from_array_image(blurred_image_array))
        projections = cubic_transformer.get_normalized_projection(target_width=MAX_WIDTH)
        self.save_as_cubic_file_set(projections)

        print("store image on objectstore")
        datastore.upload(PANORAMA_PROCESSED_CONTAINER, self.processed_path, destination=self.panorama_path, source_base=PANORAMA_PROCESSED_PATH)


    def save_as_cubic_file_set(self, projections, max_width=MAX_WIDTH):
        """
        Saves a set of cubic projections (the 6 sides of maximum resolution)
        as a Marzipano fileset
        :param projections: dict of 6 projections, keys are the faces of the cube
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
                        tile_path = Path(self.cubic_path) / f'{zoomlevel + 1}/{side}/{v_idx}'
                        tile_path.mkdir(parents=True, exist_ok=True)
                        tile.save(tile_path / f'{h_idx}.jpg')

        preview_image = Image.new('RGB', (PREVIEW_WIDTH, 6 * PREVIEW_WIDTH))
        for idx, side in enumerate(Cube.CUBE_SIDES):
            preview_image.paste(previews[side], (0, PREVIEW_WIDTH * idx))
        preview_image.save(self.cubic_path / "preview.jpg")
    '''