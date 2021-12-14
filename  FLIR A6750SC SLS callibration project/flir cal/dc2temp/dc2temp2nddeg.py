import os
import sys
import argparse
import cv2
import numpy as np
from PIL import Image
import csv
import glob
import rasterio
import matplotlib.pyplot as plt
from envi_header import find_hdr_file,read_hdr_file,write_envi_header
import spectral.io.envi as envi

parser = argparse.ArgumentParser(
    prog="dc2rad",
    usage="dc2rad.py [-h] [-t] target_dir [flags ...]",
    description="Generate a mask for marking dead pixels and/or poppers"
)
parser.add_argument(
     "-t",
    "--target_dir",
    default = 'sample_dc',
    help="Location of directory with target images."
)
parser.add_argument(
    "-c",
    "--target_coeff",
    default="coeff_7_22_2021_temp.csv",
    help="Location of target directory with coefficient values."
)
parser.add_argument(
    "-d",
    "--dead_pixels",
    default="dead_pix.tif",
    help="Location of file with dead pixel .tif image."
)
parser.add_argument(
    "-o",
    "--output",
    default ='temp_images',
    help="Location of target output directory, creates float32 image."
)
parser.add_argument(
    "-f",
    "--file_type",
    required=True,
    help="type of images being converted, options supported: \
        n: normal type (csv or tiff file) \
        i: .img file (ENVI format images)"
)

args = parser.parse_args()

# coefficient data
coefficients = np.genfromtxt(args.target_coeff,delimiter=',')
m = coefficients[:,0]
b = coefficients[:,1]

# dead pixel data
dead_path = args.dead_pixels
dead_pixels = cv2.imread(dead_path,-1)
idx = np.where(dead_pixels == np.max(dead_pixels))

# images
if args.file_type == "n":
    test_paths = glob.glob(args.target_dir + '/*')
elif args.file_type == "i":
    test_paths = glob.glob(args.target_dir + '/*.img')
    headers = glob.glob(args.target_dir + '/*.hdr')
multiple_length = len(test_paths)

print(multiple_length)

final_radiances = []
averages = []
if args.file_type == "n":
    shape_img = cv2.imread(test_paths[0],-1)
elif args.file_type == "i":
    shape_img = rasterio.open(test_paths[0])
    shape_img = shape_img.read(1)

dims =np.asarray(shape_img).shape

r = dims[0]
c = dims[1]
q = r*c

# output file
output = args.output
if not os.path.exists(output):
    os.makedirs(output)

g = 1

# loop through and attenuate each image
for e in range (multiple_length):
    fin_radiances = []
    final_radiances = []
    if args.file_type == "n":
        current_img = cv2.imread(test_paths[e],-1)
    elif args.file_type == "i":
        current_img = rasterio.open(test_paths[e])
    current_img = current_img.read(1)
    flat_current_img = current_img.flat
    new_radiances = []
    for x in range(q):
        new_radiances.append((flat_current_img[x] - b[x])/ m[x])
    averages.append(np.mean(new_radiances))
    fin_radiances = np.asarray(new_radiances).reshape(r,c)

    # average out dead pixels using roll
    dead_im = (dead_pixels/np.max(dead_pixels)) * fin_radiances
    inter = (np.roll(dead_im,  1, axis=1) + \
                    np.roll(dead_im, -1, axis=1) + \
                    np.roll(dead_im,  1, axis=0) + \
                    np.roll(dead_im, -1, axis=0)) / 4
    
    index = np.where(dead_pixels == 0.0)
    if len(index[0]) > 0:
        dead_im[index] = inter[index]

    fin_radiances[idx] = dead_im[idx]

    final_radiances = (fin_radiances.astype(np.float))

    if args.file_type == "n":
        im_name = os.path.basename(test_paths[e])
        filename = os.path.join(output,im_name)
        plt.figure
        plt.imshow(fin_radiances)
        plt.colorbar()
        plt.title(filename)
        cv2.imwrite(filename,fin_radiances.astype(np.float32))

    elif args.file_type == "i":

        lon = np.zeros(len(headers))
        lat = np.zeros(len(headers))

        im_name = os.path.basename(test_paths[e])
        extension = '.tif'
        filename = os.path.join(output,im_name+extension)
        print(filename)

        #plt.figure
        fig, ax = plt.subplots()
        im = ax.imshow(final_radiances, cmap=plt.get_cmap('gray'),vmin = np.percentile(final_radiances,2), vmax = np.percentile(final_radiances,98))
        fig.colorbar(im)
        plt.savefig('rad_plots/graph' + str(g) + '.png')

        cv2.imwrite(filename, final_radiances)    


        g+=1

    else:
        print("Invalid specified file type")