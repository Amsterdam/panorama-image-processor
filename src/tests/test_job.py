import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from numpy import iterable

import pytest
from panorama_image_processor.config import PANORAMA_INTERMEDIATE_PATH, PANORAMA_PROCESSED_PATH, PANORAMA_RAW_PATH, PANORAMA_UNPROCESSED_CONTAINER
from panorama_image_processor.job import CUBIC, EQUIRECTANGULAR, PanoramaJob, PanoramaStatus


@patch('panorama_image_processor.job.CubicTransformer')
@patch('panorama_image_processor.job.BlurPanoramaTask')
@patch('panorama_image_processor.job.DetectionTask')
@patch('panorama_image_processor.job.EquirectangularTransformer')
@patch('panorama_image_processor.job.DatastoreFactory')
@patch('panorama_image_processor.job.get_datastore_config')
def test_panormam_job(
        get_datastore_config,
        DatastoreFactory,
        EquirectangularTransformer,
        DetectionTask,
        BlurPanoramaTask,
        CubicTransformer):
    cfg =  'src', 'dst'
    ret_cfg = 'src_ds', 'dst_ds'
    get_datastore_config.side_effect = ret_cfg
    job = PanoramaJob('path', 'filename', 1.0, -1.0, 3.0, *cfg)
    assert get_datastore_config.call_args_list == [call(c) for c in cfg]
    assert DatastoreFactory.get_datastore.call_args_list == [call(c) for c in ret_cfg]
    assert job.status == PanoramaStatus.INITIAL
    for p, r in [
            ('raw_filename', PANORAMA_RAW_PATH),
            ('intermediate_filename', PANORAMA_INTERMEDIATE_PATH),
            ('processed_path', PANORAMA_PROCESSED_PATH)]:
        assert getattr(job,p) == Path(r) / 'path' / 'filename'
    assert job.equirectangular_path == job.processed_path / EQUIRECTANGULAR
    assert job.cubic_path == job.processed_path / CUBIC

    def step():
        raise KeyError('Invalid state')

    job.workflow[job.status] = step
    with pytest.raises(KeyError):
        job.process()

    job._get_raw_panorama()
    assert job._source_datastore.download_file.called_once_with(
        job.panorama_path, job.panorama_filename
    )
    assert job.status == PanoramaStatus.UNPROCESSED

    equirectangular_transformer = MagicMock()
    EquirectangularTransformer.return_value = equirectangular_transformer
    job._transform_equirectangular()
    EquirectangularTransformer.assert_called_once_with(job.raw_filename, job.heading, job.pitch, job.roll)
    equirectangular_transformer.get_projection.assert_called_once_with()
    assert job.status == PanoramaStatus.TRANSFORMED

    job._detect_regions()
    DetectionTask.assert_called_once_with(job.intermediate_filename)
    assert job.status == PanoramaStatus.DETECTED

    job._blur_regions()
    BlurPanoramaTask.assert_called_once_with()
    assert job.status == PanoramaStatus.BLURRED

    cubic_transformer = MagicMock()
    CubicTransformer.return_value = cubic_transformer
    job._package_projections()
    cubic_transformer.get_normalized_projection.assert_called_once_with()
    cubic_transformer.save_as_cubic_file_set.assert_called_once()
    assert job.status == PanoramaStatus.PACKAGED

    job._distribute()
    assert job.status == PanoramaStatus.DISTRIBUTED

    with patch('panorama_image_processor.job.os'):
        with patch('panorama_image_processor.job.shutil'):
            job._cleanup()
    assert job.status == PanoramaStatus.CLEANEDUP

    with patch('panorama_image_processor.job.os') as mock_os:
        with patch('panorama_image_processor.job.shutil'):
            mock_os.error = Exception
            mock_os.remove.side_effect = Exception()
            job._cleanup()

    job._finish_job()
    assert job.status == PanoramaStatus.DONE

@pytest.mark.parametrize('data_bytes', [b'', b'\x00' * 1024])  # 2 encountered errors, zero size and zero filled.
@patch('panorama_image_processor.job.DatastoreFactory')
@patch('panorama_image_processor.job.get_datastore_config')
def test_panorama_job_zero_size(get_datastore_config, DatastoreFactory, tmpdir, data_bytes):
    cfg =  'src', 'dst'
    ret_cfg = 'src_ds', 'dst_ds'
    get_datastore_config.side_effect = ret_cfg
    f = tmpdir.join('zero.jpg')
    f.write(data_bytes)
    job = PanoramaJob(f.dirname, f.basename, 1.0, -1.0, 3.0, *cfg)
    assert get_datastore_config.call_args_list == [call(c) for c in cfg]
    assert DatastoreFactory.get_datastore.call_args_list == [call(c) for c in ret_cfg]
    assert job.status == PanoramaStatus.INITIAL

    assert job.equirectangular_path == job.processed_path / EQUIRECTANGULAR
    assert job.cubic_path == job.processed_path / CUBIC

    job.workflow[job.status]()
    assert job._source_datastore.download_file.called_once_with(
        job.panorama_path, job.panorama_filename
    )
    assert job.status == PanoramaStatus.UNPROCESSED
    job.workflow[job.status]()
    # File is size 0
    job._destination_datastore = MagicMock()
    assert job.status == PanoramaStatus.FAILED
    assert job._destination_datastore.upload.called_with(
        PANORAMA_UNPROCESSED_CONTAINER, job.processed_path,
        destination=job.panorama_path, source_base=PANORAMA_PROCESSED_PATH
    )
    job.workflow[job.status]()
    assert job.status == PanoramaStatus.CLEANEDUP
