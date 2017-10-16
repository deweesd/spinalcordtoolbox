#!/usr/bin/env python
#########################################################################################
#
# Test function for sct_compute_hausdorff_distance
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2017 Polytechnique Montreal <www.neuro.polymtl.ca>
# Author: charley
#
# About the license: see the file LICENSE.TXT
#########################################################################################

from pandas import DataFrame

def init(param_test):
    """
    Initialize class: param_test
    """
    # initialization
    default_args = ['-i t2s/t2s_gmseg_manual.nii.gz -d t2s/t2s_gmseg_manual.nii.gz']
    param_test.max_hausdorff_distance = 1.0

    # assign default params
    if not param_test.args:
        param_test.args = default_args

    return param_test


def test_integrity(param_test):
    """
    Test integrity of function
    Parameters
    ----------
    param_test: Class defined in sct_testing.py

    Returns
    -------
    param_test
    """
    # initializations
    max_hausdorff_distance = float('nan')

    # extract name of output: hausdorff_distance.txt
    file_hausdorff = 'hausdorff_distance.txt'

    # open output segmentation
    try:
        hausdorff_txt = open(file_hausdorff, 'r')
        hausdorff_distance_lst = []
        for i, line in enumerate(hausdorff_txt):
            if line.startswith('Slice'):
                hausdorff_distance_lst.append(float(line.split(': ')[1].split(' -')[0]))
        hausdorff_txt.close()
        max_hausdorff_distance = max(hausdorff_distance_lst)
    except:
        param_test.output += 'ERROR: Cannot open output hausdorff text file: ' + file_hausdorff
        return param_test

    param_test.output += 'Max Computed Hausdorff distance: ' + str(max_hausdorff_distance)
    param_test.output += 'Hausdorff distance threshold (if Max Computed Hausdorff distance higher: fail): ' + str(param_test.max_hausdorff_distance)

    if max_hausdorff_distance > param_test.max_hausdorff_distance:
        param_test.status = 99

    # transform results into Pandas structure
    param_test.results = DataFrame(index=[param_test.path_data], data={'status': param_test.status, 'output': param_test.output, 'max_hausdorff_distance': max_hausdorff_distance, 'duration [s]': param_test.duration})

    return param_test