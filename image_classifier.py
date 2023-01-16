# -*- coding: utf-8 -*-
"""Image_Classifier.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1IzNFjiTbXdya_8j7TAe8aT4RylGUiLEi
"""

import dataclasses
import platform
from typing import List
import zipfile

import cv2
import numpy as np

# pylint: disable=g-import-not-at-top
try:
  # Import TFLite interpreter from tflite_runtime package if it's available.
  from tflite_runtime.interpreter import Interpreter
  from tflite_runtime.interpreter import load_delegate
except ImportError:
  # If not, fallback to use the TFLite interpreter from the full TF package.
  import tensorflow as tf
  Interpreter = tf.lite.Interpreter
  load_delegate = tf.lite.experimental.load_delegate
# pylint: enable=g-import-not-at-top


@dataclasses.dataclass
class ImageClassifierOptions(object):
  """A config to initialize an image classifier."""

  enable_edgetpu: bool = False
  """Enable the model to run on EdgeTPU."""

  label_allow_list: List[str] = None
  """The optional allow list of labels."""

  label_deny_list: List[str] = None
  """The optional deny list of labels."""

  max_results: int = 3
  """The maximum number of top-scored classification results to return."""

  num_threads: int = 1
  """The number of CPU threads to be used."""

  score_threshold: float = 0.0
  """The score threshold of classification results to return."""


@dataclasses.dataclass
class Category(object):
  """A result of a image classification."""
  label: str
  score: float


def edgetpu_lib_name():
  """Returns the library name of EdgeTPU in the current platform."""
  return {
      'Darwin': 'libedgetpu.1.dylib',
      'Linux': 'libedgetpu.so.1',
      'Windows': 'edgetpu.dll',
  }.get(platform.system(), None)


class ImageClassifier(str):
  """A wrapper class for a TFLite image classification model."""

  _mean = 127
  """Default mean normalization parameter for float model."""
  _std = 128
  """Default std normalization parameter for float model."""

  def __init__(
      self,
      model_path: str,
      options: ImageClassifierOptions = ImageClassifierOptions()
  ) -> None:
        
    print('model name: ', model_path)


    interpreter = Interpreter(
          model_path=model_path, num_threads=options.num_threads)
    interpreter.allocate_tensors()
    if model_path == 'model1.tflite':
      self._labels_list = labels = ['skin_cancer','skin_disorder']
    if model_path == 'model2.tflite':
      self._labels_list = labels = ['benign', 'malignant']
    if model_path == 'model3.tflite':
      self._labels_list = labels = ['Acne and Rosacea Photos', 'Actinic Keratosis Basal Cell Carcinoma and other Malignant Lesions', 'Atopic Dermatitis Photos', 'Bullous Disease Photos', 'Cellulitis Impetigo and other Bacterial Infections', 'Eczema Photos', 'Exanthems and Drug Eruptions', 'Hair Loss Photos Alopecia and other Hair Diseases', 'Herpes HPV and other STDs Photos', 'Light Diseases and Disorders of Pigmentation', 'Lupus and other Connective Tissue diseases', 'Melanoma Skin Cancer Nevi and Moles', 'Nail Fungus and other Nail Disease', 'Poison Ivy Photos and other Contact Dermatitis', 'Psoriasis pictures Lichen Planus and related diseases', 'Scabies Lyme Disease and other Infestations and Bites', 'Seborrheic Keratoses and other Benign Tumors', 'Systemic Disease', 'Tinea Ringworm Candidiasis and other Fungal Infections', 'Urticaria Hives', 'Vascular Tumors', 'Warts Molluscum and other Viral Infections', 'vasculitis']
    #else:
      #print('Invalid model name')
      
    self._input_details = interpreter.get_input_details()
    self._output_details = interpreter.get_output_details()

    self._input_height = interpreter.get_input_details()[0]['shape'][1]
    self._input_width = interpreter.get_input_details()[0]['shape'][2]

    self._is_quantized_input = interpreter.get_input_details(
    )[0]['dtype'] == np.uint8
    self._is_quantized_output = interpreter.get_output_details(
    )[0]['dtype'] == np.uint8

    self._interpreter = interpreter
    self._options = options

  def _set_input_tensor(self, image: np.ndarray) -> None:
    """Sets the input tensor."""
    tensor_index = self._input_details[0]['index']
    input_tensor = self._interpreter.tensor(tensor_index)()[0]
    input_tensor[:, :] = image

  def _preprocess(self, image: np.ndarray) -> np.ndarray:
    """Preprocess the input image as required by the TFLite model."""
    input_tensor = cv2.resize(image, (self._input_width, self._input_height))
    # Normalize the input if it's a float model (aka. not quantized)
    if not self._is_quantized_input:
      input_tensor = (np.float32(input_tensor) - self._mean) / self._std
    return input_tensor

  # TODO(khanhlvg): Migrate to TensorImage once it's published.
  def classify(self, image: np.ndarray) -> List[Category]:
    """Classify an input image.
    Args:
        image: A [height, width, 3] RGB image.
    Returns:
        A list of prediction result. Sorted by probability descending.
    """
    #image = self._preprocess(image)
    self._set_input_tensor(image)
    self._interpreter.invoke()
    output_tensor = np.squeeze(
        self._interpreter.get_tensor(self._output_details[0]['index']))
        
    print(output_tensor)

    return self._postprocess(output_tensor)

  def _postprocess(self, output_tensor: np.ndarray) -> List[Category]:
    """Post-process the output tensor into a list of Category objects.
    Args:
        output_tensor: Output tensor of TFLite model.
    Returns:
        A list of prediction result.
    """

    # If the model is quantized (uint8 data), then dequantize the results
    if self._is_quantized_output:
      scale, zero_point = self._output_details[0]['quantization']
      output_tensor = scale * (output_tensor - zero_point)

    # Sort output by probability descending.
    prob_descending = sorted(
        range(len(output_tensor)), key=lambda k: output_tensor[k], reverse=True)

    categories = [
        Category(label=self._labels_list[idx], score=output_tensor[idx])
        for idx in prob_descending
    ]

    # Filter out classification in deny list
    filtered_results = categories
    
    if self._options.label_deny_list is not None:
      filtered_results = list(
          filter(
              lambda category: category.label not in self._options.
              label_deny_list, filtered_results))

    # Keep only classification in allow list
    if self._options.label_allow_list is not None:
      filtered_results = list(
          filter(
              lambda category: category.label in self._options.label_allow_list,
              filtered_results))

    # Filter out classification in score threshold
    if self._options.score_threshold is not None:
      filtered_results = list(
          filter(
              lambda category: category.score >= self._options.score_threshold,
              filtered_results))

    # Only return maximum of max_results classification.
    if self._options.max_results > 0:
      result_count = min(len(filtered_results), self._options.max_results)
      filtered_results = filtered_results[:result_count]

    return filtered_results