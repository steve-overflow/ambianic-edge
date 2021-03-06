"""Test fall detection pipe element."""
from ambianic.pipeline.ai.fall_detect import FallDetector
from ambianic.pipeline.ai.object_detect import ObjectDetector
from ambianic.pipeline import PipeElement
import os
import time
from PIL import Image


def _fall_detect_config():

    _dir = os.path.dirname(os.path.abspath(__file__))
    _good_tflite_model = os.path.join(
        _dir,
        'posenet_mobilenet_v1_100_257x257_multi_kpt_stripped.tflite'
        )
    _good_edgetpu_model = os.path.join(
        _dir,
        'posenet_mobilenet_v1_075_721_1281_quant_decoder_edgetpu.tflite'
        )
    _good_labels = os.path.join(_dir, 'pose_labels.txt')
    config = {
        'model': {
            'tflite': _good_tflite_model,
            'edgetpu': _good_edgetpu_model,
            },
        'labels': _good_labels,
        'top_k': 3,
        'confidence_threshold': 0.8,
    }
    return config


def _get_image(file_name=None):
    assert file_name
    _dir = os.path.dirname(os.path.abspath(__file__))
    image_file = os.path.join(_dir, file_name)
    img = Image.open(image_file)
    return img


class _OutPipeElement(PipeElement):

    def __init__(self, sample_callback=None):
        super().__init__()
        assert sample_callback
        self._sample_callback = sample_callback

    def receive_next_sample(self, **sample):
        self._sample_callback(**sample)


def test_model_inputs():
    """Verify against known model inputs."""
    config = _fall_detect_config()
    fall_detector = FallDetector(**config)
    tfe = fall_detector._tfengine

    samples = tfe.input_details[0]['shape'][0]
    assert samples == 1
    height = tfe.input_details[0]['shape'][1]
    assert height == 257
    width = tfe.input_details[0]['shape'][2]
    assert width == 257
    colors = tfe.input_details[0]['shape'][3]
    assert colors == 3


def test_fall_detection_thumbnail_present():
    """Expected to receive thumnail in result if image is provided and poses are detected."""
    config = _fall_detect_config()
    result = None

    def sample_callback(image=None, thumbnail=None, inference_result=None, **kwargs):
        nonlocal result
        result = image is not None and thumbnail is not None and inference_result is not None

    fall_detector = FallDetector(**config)

    output = _OutPipeElement(sample_callback=sample_callback)
    fall_detector.connect_to_next_element(output)

    img_1 = _get_image(file_name='fall_img_1.png')
    fall_detector.receive_next_sample(image=img_1)

    assert result is True


def test_fall_detection_case_1():
    """Expected to not detect a fall as key-points are not detected."""
    config = _fall_detect_config()
    result = None

    def sample_callback(image=None, inference_result=None, **kwargs):
        nonlocal result
        result = inference_result

    fall_detector = FallDetector(**config)

    output = _OutPipeElement(sample_callback=sample_callback)
    fall_detector.connect_to_next_element(output)

    img_1 = _get_image(file_name='fall_img_1.png')
    img_2 = _get_image(file_name='fall_img_3.png')
    fall_detector.receive_next_sample(image=img_1)
    fall_detector.min_time_between_frames = 0.01
    time.sleep( fall_detector.min_time_between_frames )
    fall_detector.receive_next_sample(image=img_2)

    assert not result
    
def test_fall_detection_case_2_1():
    """Expected to not detect a fall even though key-points are detected and the angle criteria is met. However the time distance between frames is too short."""
    config = _fall_detect_config()
    result = None

    def sample_callback(image=None, inference_result=None, **kwargs):
        nonlocal result
        result = inference_result

    fall_detector = FallDetector(**config)

    output = _OutPipeElement(sample_callback=sample_callback)
    
    fall_detector.connect_to_next_element(output)

    img_1 = _get_image(file_name='fall_img_1.png')
    img_2 = _get_image(file_name='fall_img_2.png')
    start_time = time.monotonic()
    fall_detector.receive_next_sample(image=img_1)
    end_time = time.monotonic()
    safe_min = end_time-start_time+1
    # set min time to a sufficiently big number to ensure test passes on slow environments
    # the goal is to simulate two frames that are too close in time to be considered for a fall detection sequence
    fall_detector.min_time_between_frames = safe_min
    fall_detector.receive_next_sample(image=img_2)

    assert result is None

def test_fall_detection_case_2_2():
    """Expected to detect a fall because key-points are detected, the angle criteria is met and the time distance between frames is not too short."""
    config = _fall_detect_config()
    result = None

    def sample_callback(image=None, inference_result=None, **kwargs):
        nonlocal result
        result = inference_result

    fall_detector = FallDetector(**config)

    output = _OutPipeElement(sample_callback=sample_callback)
    
    fall_detector.connect_to_next_element(output)

    img_1 = _get_image(file_name='fall_img_1.png')
    img_2 = _get_image(file_name='fall_img_2.png')
    fall_detector.receive_next_sample(image=img_1)
    fall_detector.min_time_between_frames = 0.01
    time.sleep( fall_detector.min_time_between_frames )
    fall_detector.receive_next_sample(image=img_2)

    assert result
    assert len(result) == 1
    category, confidence, box, angle = result[0]
    assert category == 'FALL'
    assert confidence > 0.7
    assert angle > 60

def test_fall_detection_case_3():
    """Expect to detect a fall as key-points are detected by rotating the image."""
    config = _fall_detect_config()
    result = None

    def sample_callback(image=None, inference_result=None, **kwargs):
        nonlocal result
        result = inference_result

    fall_detector = FallDetector(**config)

    output = _OutPipeElement(sample_callback=sample_callback)
    
    fall_detector.connect_to_next_element(output)

    img_1 = _get_image(file_name='fall_img_11.png')
    img_2 = _get_image(file_name='fall_img_12.png')
    fall_detector.receive_next_sample(image=img_1)
    # set min time to a small number to speed up testing
    fall_detector.min_time_between_frames = 0.01
    time.sleep( fall_detector.min_time_between_frames )
    fall_detector.receive_next_sample(image=img_2)

    assert result
    assert len(result) == 1
    category, confidence, box, angle = result[0]
    assert category == 'FALL'
    assert confidence > 0.3
    assert angle > 60

def test_fall_detection_case_4():
    """No Fall"""
    config = _fall_detect_config()
    result = None

    def sample_callback(image=None, inference_result=None, **kwargs):
        nonlocal result
        result = inference_result

    fall_detector = FallDetector(**config)

    output = _OutPipeElement(sample_callback=sample_callback)
    
    fall_detector.connect_to_next_element(output)

    img_1 = _get_image(file_name='fall_img_1.png')
    img_2 = _get_image(file_name='fall_img_4.png')
    fall_detector.receive_next_sample(image=img_1)
    fall_detector.min_time_between_frames = 0.01
    time.sleep( fall_detector.min_time_between_frames )
    fall_detector.receive_next_sample(image=img_2)

    assert not result

def test_background_image():
    """Expect to not detect anything interesting in a background image."""
    config = _fall_detect_config()
    result = None

    def sample_callback(image=None, thumbnail=None, inference_result=None, **kwargs):
        nonlocal result
        result = image is not None and thumbnail is not None and inference_result is None
    fall_detector = FallDetector(**config)
    output = _OutPipeElement(sample_callback=sample_callback)
    fall_detector.connect_to_next_element(output)
    img = _get_image(file_name='background.jpg')
    fall_detector.receive_next_sample(image=img)
    fall_detector.min_time_between_frames = 0.01
    time.sleep( fall_detector.min_time_between_frames )
    img = _get_image(file_name='background.jpg')
    fall_detector.receive_next_sample(image=img)
    assert result is True


def test_no_sample():
    """Expect element to pass empty sample to next element."""
    config = _fall_detect_config()
    result = False

    def sample_callback(image=None, inference_result=None, **kwargs):
        nonlocal result
        result = image is None and inference_result is None
    fall_detector = FallDetector(**config)
    output = _OutPipeElement(sample_callback=sample_callback)
    fall_detector.connect_to_next_element(output)
    fall_detector.receive_next_sample()
    assert result is True


def test_bad_sample_good_sample():
    """One bad sample should not prevent good samples from being processed."""
    config = _fall_detect_config()
    result = 'nothing passed to me'

    def sample_callback(image=None, inference_result=None, **kwargs):
        nonlocal result
        result = inference_result
    object_detector = ObjectDetector(**config)
    output = _OutPipeElement(sample_callback=sample_callback)
    object_detector.connect_to_next_element(output)
    # bad sample
    object_detector.receive_next_sample(image=None)
    assert result == 'nothing passed to me'

    # good sample
    fall_detector = FallDetector(**config)
    fall_detector.connect_to_next_element(output)

    img_1 = _get_image(file_name='fall_img_1.png')
    img_2 = _get_image(file_name='fall_img_2.png')
    fall_detector.receive_next_sample(image=img_1)
    fall_detector.min_time_between_frames = 0.01
    time.sleep( fall_detector.min_time_between_frames )
    fall_detector.receive_next_sample(image=img_2)

    assert result
    assert len(result) == 1
    category, confidence, box, angle = result[0]
    assert category == 'FALL'
    assert confidence > 0.7
    assert angle > 60
