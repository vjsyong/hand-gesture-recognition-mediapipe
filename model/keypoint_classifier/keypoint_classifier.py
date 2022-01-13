#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import numpy as np

use_tflite_runtime = False
try:
    import tensorflow as tf
except:
    import tflite_runtime.interpreter as tflite
    use_tflite_runtime = True


class KeyPointClassifier(object):
    def __init__(
        self,
        model_path=None,
        num_threads=1,
    ):
        if model_path == None:
            current_dir = os.path.dirname(os.path.realpath(__file__))
            self.model_path = current_dir + "/keypoint_classifier.tflite"

        if use_tflite_runtime:
            self.interpreter = tflite.Interpreter(model_path=self.model_path,
                                               num_threads=num_threads)
        else:
            self.interpreter = tf.lite.Interpreter(model_path=self.model_path,
                                               num_threads=num_threads)

        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

    def __call__(
        self,
        landmark_list,
    ):
        input_details_tensor_index = self.input_details[0]['index']
        self.interpreter.set_tensor(
            input_details_tensor_index,
            np.array([landmark_list], dtype=np.float32))
        self.interpreter.invoke()

        output_details_tensor_index = self.output_details[0]['index']

        result = self.interpreter.get_tensor(output_details_tensor_index)

        result_index = np.argmax(np.squeeze(result))

        return result_index, np.squeeze(result)[result_index]
