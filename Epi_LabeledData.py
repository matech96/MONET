import cv2
from utils import cpm_utils
from utils import tf_utils
import numpy as np
import math
import tensorflow as tf
import time
import random
import matplotlib.pyplot as plt
from Utility.Epi_class import *
from Utility.DataUtility import *
from Utility.GeometryUtility import *

tfr_file = 'training_data.tfrecords'
dataset_dir = ''

SHOW_INFO = False
img_size = 368
heatmap_size = 46
num_of_joints = 19
gaussian_radius = 1



def _bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

def _int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int32List(value=[value]))

def _float32_feature(value):
    return tf.train.Feature(float_list=tf.train.FloatList(value=value))


tfr_writer = tf.python_io.TFRecordWriter(tfr_file)

img_count = 0

vCamera = LoadCameraData('camera.txt')
vCamera = LoadCameraIntrinsicData('/intrinsic.txt', vCamera)

gt_content = open('label.txt', 'rb').readlines()

for idx, line in enumerate(gt_content):
    line = line.split()
    cur_img_path = "image/"+ line[0]
    cur_img = cv2.imread(cur_img_path)

    for iCamera in range(len(vCamera)):
        if vCamera[iCamera].frame == np.int(line[2]):
            camera_ref = vCamera[iCamera]

    print(cur_img_path)

    tmp = [float(x) for x in line[3:7]]
    cur_hand_bbox = [min([tmp[1], tmp[3]]), min([tmp[0], tmp[2]]), max([tmp[1], tmp[3]]), max([tmp[0], tmp[2]])]
    if cur_hand_bbox[0] < 0: cur_hand_bbox[0] = 0
    if cur_hand_bbox[1] < 0: cur_hand_bbox[1] = 0
    if cur_hand_bbox[2] > cur_img.shape[1]: cur_hand_bbox[2] = cur_img.shape[1]
    if cur_hand_bbox[3] > cur_img.shape[0]: cur_hand_bbox[3] = cur_img.shape[0]

    cur_hand_joints_y = [float(i) for i in line[7:60:2]]

    cur_hand_joints_x = [float(i) for i in line[8:60:2]]

    cur_img = cur_img[int(float(cur_hand_bbox[1])):int(float(cur_hand_bbox[3])),
              int(float(cur_hand_bbox[0])):int(float(cur_hand_bbox[2])), :]
    cur_hand_joints_x = [x - cur_hand_bbox[0] for x in cur_hand_joints_x]
    cur_hand_joints_y = [x - cur_hand_bbox[1] for x in cur_hand_joints_y]
    # print(cur_img.shape)
    # print(cur_hand_joints_x)

    # print([cur_hand_joints_x[0], cur_hand_joints_y[0]])

    output_image = np.ones(shape=(img_size, img_size, 3)) * 128
    heatmap_output_image = np.ones(shape=(heatmap_size, heatmap_size, 3)) * 128
    output_heatmaps = np.zeros((heatmap_size, heatmap_size, num_of_joints))
    output_limbs_heatmaps = np.zeros((heatmap_size, heatmap_size, num_of_limbs*2))

    # Resize and pad image to fit output image size
    # if h > w

    if cur_img.shape[0] > cur_img.shape[1]:
        img_scale = img_size / (cur_img.shape[0] * 1.0)
        # Resize image
        image = cv2.resize(cur_img, (0, 0), fx=img_scale, fy=img_scale, interpolation=cv2.INTER_LANCZOS4)
        # heatmap_image = cv2.resize(cur_img, (0, 0), fx=img_scale, fy=img_scale, interpolation=cv2.INTER_LANCZOS4)

        offset_x = int(img_size / 2 - math.floor(image.shape[1] / 2))
        offset_y = 0
    else:
        img_scale = img_size / (cur_img.shape[1] * 1.0)
        image = cv2.resize(cur_img, (0, 0), fx=img_scale, fy=img_scale, interpolation=cv2.INTER_LANCZOS4)
        # heatmap_image = cv2.resize(cur_img, (0, 0), fx=img_scale, fy=img_scale, interpolation=cv2.INTER_LANCZOS4)

        offset_x = 0
        offset_y = int(img_size / 2 - math.floor(image.shape[0] / 2))

    output_image[offset_y:offset_y+image.shape[0], offset_x:offset_x+image.shape[1],:] = image
    for i in range(num_of_joints):
         ht = cpm_utils.make_gaussian(img_size, float(gaussian_radius)*float(img_size)/heatmap_size, [offset_x+cur_hand_joints_x[i]*img_scale, offset_y+cur_hand_joints_y[i]*img_scale])
         ht = cv2.resize(ht, (0, 0), fx=float(heatmap_size)/img_size, fy=float(heatmap_size)/img_size, interpolation=cv2.INTER_LANCZOS4)
         output_heatmaps[:, :, i] = ht



    cropping_param = [int(float(cur_hand_bbox[0])),
                      int(float(cur_hand_bbox[1])),
                      int(float(cur_hand_bbox[2])),
                      int(float(cur_hand_bbox[3])),
                      offset_x,
                      offset_y,
                      img_scale
                      ]

    # Create background map
    output_background_map = np.ones((heatmap_size, heatmap_size)) - np.amax(output_heatmaps, axis=2)
    output_heatmaps = np.concatenate((output_heatmaps, output_background_map.reshape((heatmap_size, heatmap_size, 1))),
                                     axis=2)


    # coords_set = np.concatenate(
    #     (np.reshape(cur_hand_joints_x, (num_of_joints, 1)), np.reshape(cur_hand_joints_y, (num_of_joints, 1))), axis=1)

    output_image_raw = output_image.astype(np.uint8).tostring()
    output_heatmaps_raw = output_heatmaps.flatten().tolist()
    # output_coords_raw = coords_set.flatten().tolist()
    output_cropping_param_raw = cropping_param
    output_R_raw = camera_ref.R.flatten().tolist()
    output_C_raw = camera_ref.C.flatten().tolist()
    output_K_raw = camera_ref.K.flatten().tolist()

    raw_sample = tf.train.Example(features=tf.train.Features(
        feature={'image': _bytes_feature(output_image_raw),
                 'heatmaps': _float32_feature(output_heatmaps_raw),
                 'cropping_param': _float32_feature(output_cropping_param_raw),
                 'K': _float32_feature(output_K_raw),
                 'R': _float32_feature(output_R_raw),
                 'C': _float32_feature(output_C_raw),
                 'frame': _float32_feature([np.float(line[1]), np.float(line[2])])}))

    tfr_writer.write(raw_sample.SerializeToString())

    img_count += 1

tfr_writer.close()
