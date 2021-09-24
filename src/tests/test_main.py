from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from panorama_image_processor.__main__ import get_processing_queue, main, peek, flush, speed, prepare, fill, queue

NR_WORKERS = 2

@patch('panorama_image_processor.__main__.get_processing_queue')
@patch('panorama_image_processor.__main__.PanoramaWorker')
@patch('panorama_image_processor.__main__.WORKERS', NR_WORKERS)
def test_main(PanoramaWorker, get_processing_queue):
    processing_queue = MagicMock()
    get_processing_queue.return_value = processing_queue
    workers = [MagicMock() for _ in range(NR_WORKERS)]
    PanoramaWorker.side_effect = workers
    main()
    PanoramaWorker.call_args = [processing_queue, processing_queue]
    for worker in workers:
        worker.join.assert_called_once_with()
        worker.start.assert_called_once_with()


@patch('panorama_image_processor.__main__.get_processing_queue')
@patch('panorama_image_processor.__main__.queue_peek')
def test_peek(queue_peek, get_processing_queue):
    processing_queue = MagicMock()
    get_processing_queue.return_value = processing_queue
    runner = CliRunner()
    result = runner.invoke(peek)
    assert result.exit_code == 0
    queue_peek.assert_called_once_with(processing_queue)
    get_processing_queue.assert_called_once()


@patch('panorama_image_processor.__main__.get_processing_queue')
@patch('panorama_image_processor.__main__.queue_fill')
def test_fill(queue_fill, get_processing_queue, tmpdir):
    processing_queue = MagicMock()
    get_processing_queue.return_value = processing_queue
    runner = CliRunner()
    p = tmpdir.join('msgfile.txt')
    p.write('hello')
    result = runner.invoke(fill, [p.strpath])
    assert result.exit_code == 0
    get_processing_queue.assert_called_once()
    queue_fill.assert_called_once()


@patch('panorama_image_processor.__main__.queue_prepare')
def test_prepare(queue_prepare):
    processing_queue = MagicMock()
    get_processing_queue.return_value = processing_queue
    runner = CliRunner()
    result = runner.invoke(prepare, [
            '--limit', '100',
            'outfile',
            'container',
    ])
    assert result.exit_code == 0
    queue_prepare.assert_called_once()


@patch('panorama_image_processor.__main__.get_processing_queue')
@patch('panorama_image_processor.__main__.queue_speed')
def test_speed(queue_speed, get_processing_queue):
    processing_queue = MagicMock()
    get_processing_queue.return_value = processing_queue
    runner = CliRunner()
    result = runner.invoke(speed)
    assert result.exit_code == 0
    queue_speed.assert_called_once_with(processing_queue, 10)
    get_processing_queue.assert_called_once()

@patch('panorama_image_processor.__main__.get_processing_queue')
@patch('panorama_image_processor.__main__.queue_flush')
def test_flush(queue_flush, get_processing_queue):
    processing_queue = MagicMock()
    get_processing_queue.return_value = processing_queue
    runner = CliRunner()
    result = runner.invoke(flush)
    assert result.exit_code == 0
    queue_flush.assert_called_once_with(processing_queue)
    get_processing_queue.assert_called_once()


@patch('panorama_image_processor.__main__.AzureStorageQueue')
def test_get_processing_queue(AzureStorageQueue):
    AzureStorageQueue.return_value = 'bello'
    assert 'bello' == get_processing_queue()
    AzureStorageQueue.asset_called_once_with('panorama-processing-queue')
