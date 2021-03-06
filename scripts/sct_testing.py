#!/usr/bin/env python
#
# Test major functions.
#
# In The following fields should be defined under the init() function of each test script:
#   param_test.list_fname_gt     list containing the relative file name for ground truth data. See test_sct_propseg
#
# Authors: Julien Cohen-Adad, Benjamin De Leener, Augustin Roux

# TODO: list functions to test in help (do a search in testing folder)
# TODO: find a way to be able to have list of arguments and loop across list elements.
# TODO: do something about this ugly 'output.nii.gz'

import sys, io, os, time, random, copy, shlex, importlib, multiprocessing
import signal

from pandas import DataFrame

from msct_parser import Parser
import sct_utils as sct

# get path of SCT
path_script = os.path.dirname(__file__)
path_sct = os.path.dirname(path_script)
sys.path.append(os.path.join(path_sct, 'testing'))


# Parameters
class Param:
    def __init__(self):
        self.download = 0
        self.path_data = 'sct_testing_data'  # path to the testing data
        self.path_output = []  # list of output folders
        self.function_to_test = None
        self.remove_tmp_file = 0
        self.verbose = 1
        self.path_tmp = None
        self.args = []  # list of input arguments to the function
        self.args_with_path = ''  # input arguments to the function, with path
        # self.list_fname_gt = []  # list of fname for ground truth data
        self.contrast = ''  # folder containing the data and corresponding to the contrast. Could be t2, t1, t2s, etc.
        self.output = ''  # output string
        self.results = ''  # results in Panda DataFrame
        self.redirect_stdout = True  # for debugging, set to 0. Otherwise set to 1.
        self.fname_log = None


# define nice colors
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


# PARSER
# ==========================================================================================
def get_parser():
    import argparse

    param_default = Param()

    parser = argparse.ArgumentParser(
     description="Crash and integrity testing for functions of the Spinal Cord Toolbox. Internet connection is required for downloading testing data.",
    )

    parser.add_argument("--function", "-f",
     help="Test this specific script (eg. 'sct_propseg').",
     nargs="+",
    )

    def arg_jobs(s):
        jobs = int(s)
        if jobs > 0:
            pass
        elif jobs == 0:
            jobs = None
        else:
            raise ValueError()
        return jobs

    parser.add_argument("--download", "-d",
     choices=("0", "1"),
     default=param_default.download,
    )
    parser.add_argument("--path", "-p",
     help='Path to testing data. NB: no need to set if using "-d 1"',
     default=param_default.path_data,
    )
    parser.add_argument("--remove-temps", "-r",
     choices=("0", "1"),
     help='Remove temporary files.',
     default=param_default.remove_tmp_file,
    )
    parser.add_argument("--jobs", "-j",
     type=arg_jobs,
     help="# of simultaneous tests to run (jobs). 0 means # of available CPU threads",
     default=arg_jobs(0),
    )

    return parser


def process_function(fname, param):
    """
    """
    param.function_to_test = fname
    # display script name
    # load modules of function to test
    module_testing = importlib.import_module('test_' + fname)
    # initialize default parameters of function to test
    param.args = []
    # param.list_fname_gt = []
    # param.fname_groundtruth = ''
    param = module_testing.init(param)
    # loop over parameters to test
    list_status_function = []
    list_output = []
    for i in range(0, len(param.args)):
        param_test = copy.deepcopy(param)
        param_test.default_args = param.args
        param_test.args = param.args[i]
        param_test.test_integrity = True
        # if list_fname_gt is not empty, assign it
        # if param_test.list_fname_gt:
        #     param_test.fname_gt = param_test.list_fname_gt[i]
        # test function
        try:
            param_test = test_function(param_test)
        except Exception as e:
            list_status_function.append(1)
            list_output.append("TODO exception: %s" % e)
        else:
            list_status_function.append(param_test.status)
            list_output.append(param_test.output)

    return list_output, list_status_function

def process_function_multiproc(fname, param):
    """ Wrapper that makes ^C work in multiprocessing code """
    # Ignore SIGINT, parent will take care of the clean-up
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    return process_function(fname, param)


# Main
# ==========================================================================================
def main(args=None):

    # initializations
    list_status = []
    param = Param()

    # check user arguments
    if args is None:
        args = sys.argv[1:]

    # get parser info
    parser = get_parser()

    arguments = parser.parse_args(args)

    param.download = int(arguments.download)
    param.path_data = arguments.path
    functions_to_test = arguments.function
    param.remove_tmp_file = int(arguments.remove_temps)
    jobs = arguments.jobs

    start_time = time.time()

    # get absolute path and add slash at the end
    param.path_data = os.path.abspath(param.path_data)

    # check existence of testing data folder
    if not os.path.isdir(param.path_data) or param.download:
        downloaddata(param)

    # display path to data
    sct.printv('\nPath to testing data: ' + param.path_data, param.verbose)

    # create temp folder that will have all results and go in it
    param.path_tmp = sct.tmp_create(verbose=0)
    curdir = os.getcwd()
    os.chdir(param.path_tmp)

    # get list of all scripts to test
    list_functions = fill_functions()
    if functions_to_test:
        for f in functions_to_test:
            if f not in list_functions:
                sct.printv('Command-line usage error: Function "%s" is not part of the list of testing functions' % function_to_test, type='error')
        list_functions = functions_to_test

    try:
        if jobs != 1:
            pool = multiprocessing.Pool(processes=jobs)

            results = list()
            # loop across functions and run tests
            for f in list_functions:
                res = pool.apply_async(process_function_multiproc, (f, param,))
                results.append(res)

        for idx_function, f in enumerate(list_functions):
            print_line('Checking ' + f)
            if jobs == 1:
                res = process_function(f, param)
            else:
                res = results[idx_function].get()

            list_output, list_status_function = res
            # manage status
            if any(list_status_function):
                if 1 in list_status_function:
                    print_fail()
                    status = 1
                else:
                    print_warning()
                    status = 99
                for output in list_output:
                    for line in output.splitlines():
                        print("   %s" % line)
            else:
                print_ok()
                status = 0
            # append status function to global list of status
            list_status.append(status)
    except KeyboardInterrupt:
        print("Keyboard Interrupt")
        if jobs != 1:
            pool.terminate()
            pool.join()
        raise

    print('status: ' + str(list_status))

    # display elapsed time
    elapsed_time = time.time() - start_time
    sct.printv('Finished! Elapsed time: ' + str(int(round(elapsed_time))) + 's\n')

    # come back
    os.chdir(curdir)

    # remove temp files
    if param.remove_tmp_file:
        sct.printv('\nRemove temporary files...', 0)
        sct.rmtree(param.path_tmp)

    e = 0
    if sum(list_status) != 0:
        e = 1
    # print(e)

    sys.exit(e)


def downloaddata(param):
    """
    Download testing data from internet.
    Parameters
    ----------
    param

    Returns
    -------
    None
    """
    sct.printv('\nDownloading testing data...', param.verbose)
    import sct_download_data
    sct_download_data.main(['-d', 'sct_testing_data'])


# list of all functions to test
# ==========================================================================================
def fill_functions():
    functions = [
        'sct_analyze_lesion',
        'sct_analyze_texture',
        'sct_apply_transfo',
        'sct_compute_ernst_angle',
        'sct_compute_hausdorff_distance',
        'sct_compute_mtr',
        'sct_compute_mscc',
        'sct_compute_snr',
        'sct_concat_transfo',
        'sct_convert',
        # 'sct_convert_binary_to_trilinear',  # not useful
        'sct_create_mask',
        'sct_crop_image',
        'sct_dice_coefficient',
        'sct_deepseg_gm',
        'sct_deepseg_sc',
        'sct_detect_pmj',
        'sct_dmri_compute_dti',
        'sct_dmri_concat_bvals',
        'sct_dmri_concat_bvecs',
        'sct_dmri_create_noisemask',
        'sct_dmri_compute_bvalue',
        'sct_dmri_moco',
        'sct_dmri_separate_b0_and_dwi',
        'sct_dmri_transpose_bvecs',
        # 'sct_documentation',
        'sct_extract_metric',
        # 'sct_flatten_sagittal',
        'sct_fmri_compute_tsnr',
        'sct_fmri_moco',
        'sct_get_centerline',
        'sct_image',
        # 'sct_invert_image',  # function not available from command-line
        'sct_label_utils',
        'sct_label_vertebrae',
        'sct_maths',
        'sct_merge_images',
        # 'sct_pipeline',
        'sct_process_segmentation',
        'sct_propseg',
        'sct_register_graymatter',
        'sct_register_multimodal',
        'sct_register_to_template',
        'sct_resample',
        'sct_segment_graymatter',
        'sct_smooth_spinalcord',
        'sct_straighten_spinalcord',
        'sct_warp_template',
    ]
    return functions


# print without carriage return
# ==========================================================================================
def print_line(string):
    import sys
    sys.stdout.write(string + make_dot_lines(string))
    sys.stdout.flush()


# fill line with dots
# ==========================================================================================
def make_dot_lines(string):
    if len(string) < 52:
        dot_lines = '.' * (52 - len(string))
        return dot_lines
    else:
        return ''


# print in color
# ==========================================================================================
def print_ok():
    sct.log.info("[" + bcolors.OKGREEN + "OK" + bcolors.ENDC + "]")


def print_warning():
    sct.log.warning("[" + bcolors.WARNING + "WARNING" + bcolors.ENDC + "]")


def print_fail():
    sct.log.error("[" + bcolors.FAIL + "FAIL" + bcolors.ENDC + "]")


# write to log file
# ==========================================================================================
def write_to_log_file(fname_log, string, mode='w', prepend=False):
    """
    status, output = sct.run('echo $SCT_DIR', 0)
    path_logs_dir = os.path.join(output, "testing", "logs")

    if not os.path.isdir(path_logs_dir):
        os.makedirs(path_logs_dir)
    mode: w: overwrite, a: append, p: prepend
    """
    string_to_append = ''
    string = "test ran at " + time.strftime("%y%m%d%H%M%S") + "\n" \
             + fname_log \
             + string
    # open file
    try:
        # if prepend, read current file and then overwrite
        if prepend:
            f = open(fname_log, 'r')
            # string_to_append = '\n\nOUTPUT:\n--\n' + f.read()
            string_to_append = f.read()
            f.close()
        f = open(fname_log, mode)
    except Exception as ex:
        raise Exception('WARNING: Cannot open log file.')
    f.write(string + string_to_append + '\n')
    f.close()


# init_testing
# ==========================================================================================
def test_function(param_test):
    """

    Parameters
    ----------
    file_testing

    Returns
    -------
    path_output [str]: path where to output testing data
    """
    sct.log.debug("Starting test function")

    # load modules of function to test
    module_function_to_test = importlib.import_module(param_test.function_to_test)
    module_testing = importlib.import_module('test_' + param_test.function_to_test)

    # retrieve subject name
    subject_folder = os.path.basename(param_test.path_data)

    # build path_output variable
    path_testing = os.getcwd()
    param_test.path_output = sct.tmp_create(basename=(param_test.function_to_test + '_' + subject_folder), verbose=0)

    # get parser information
    parser = module_function_to_test.get_parser()
    dict_args = parser.parse(shlex.split(param_test.args), check_file_exist=False)
    # TODO: if file in list does not exist, raise exception and assign status=200
    # add data path to each input argument
    dict_args_with_path = parser.add_path_to_file(copy.deepcopy(dict_args), param_test.path_data, input_file=True)
    # add data path to each output argument
    dict_args_with_path = parser.add_path_to_file(copy.deepcopy(dict_args_with_path), param_test.path_output, input_file=False, output_file=True)
    # save into class
    param_test.dict_args_with_path = dict_args_with_path
    param_test.args_with_path = parser.dictionary_to_string(dict_args_with_path)

    # check if parser has key '-ofolder' that has not been added already. If so, then assign output folder
    if "-ofolder" in parser.options and '-ofolder' not in dict_args_with_path:
        param_test.args_with_path += ' -ofolder ' + param_test.path_output

    # check if parser has key '-o' that has not been added already. If so, then assign output folder
    # Note: this -o case has been added for compatibility with sct_deepseg_gm, which does not have -ofolder flag
    if "-o" in parser.options and '-o' not in dict_args_with_path:
        param_test.args_with_path += ' -o ' + os.path.join(param_test.path_output, 'output.nii.gz')

    # open log file
    # Note: the statement below is not included in the if, because even if redirection does not occur, we want the file to be create otherwise write_to_log will fail

    if param_test.fname_log is None:
        param_test.fname_log = os.path.join(param_test.path_output, param_test.function_to_test + '.log')

    # redirect to log file
    if param_test.redirect_stdout:
        file_handler = sct.add_file_handler_to_logger(param_test.fname_log)
    sct.log.debug("logging to file")

    # initialize panda dataframe
    sct.log.debug("Init dataframe")
    param_test.results = DataFrame(index=[subject_folder],
                                   data={'status': 0,
                                         'duration': 0,
                                         'output': '',
                                         'path_data': param_test.path_data,
                                         'path_output': param_test.path_output})

    # retrieve input file (will be used later for integrity testing)
    if '-i' in dict_args:
        # check if list in case of multiple input files
        if not isinstance(dict_args_with_path['-i'], list):
            list_file_to_check = [dict_args_with_path['-i']]
            # assign field file_input for integrity testing
            param_test.file_input = dict_args['-i'].split('/')[-1]
            # update index of dataframe by appending file name for more clarity
            param_test.results = param_test.results.rename({subject_folder: os.path.join(subject_folder, dict_args['-i'])})
        else:
            list_file_to_check = dict_args_with_path['-i']
            # TODO: assign field file_input for integrity testing
        for file_to_check in list_file_to_check:
            # file_input = file_to_check.split('/')[1]
            # Check if input files exist
            if not (os.path.isfile(file_to_check)):
                param_test.status = 200
                param_test.output += '\nERROR: This input file does not exist: ' + file_to_check
                write_to_log_file(param_test.fname_log, param_test.output, 'w')
                return update_param(param_test)

    # retrieve ground truth (will be used later for integrity testing)
    if '-igt' in dict_args:
        param_test.fname_gt = dict_args_with_path['-igt']
        # Check if ground truth files exist
        if not os.path.isfile(param_test.fname_gt):
            param_test.status = 201
            param_test.output += '\nERROR: The following file used for ground truth does not exist: ' + param_test.fname_gt
            write_to_log_file(param_test.fname_log, param_test.output, 'w')
            return update_param(param_test)

    # go to specific testing directory
    os.chdir(param_test.path_output)

    # run command
    cmd = param_test.function_to_test + param_test.args_with_path
    param_test.output += '\n====================================================================================================\n' + cmd + '\n====================================================================================================\n\n'  # copy command
    time_start = time.time()
    try:
        param_test.status, o = sct.run(cmd, verbose=0)
        if param_test.status:
            raise Exception
    except Exception as err:
        param_test.status = 1
        param_test.output += str(err)
        write_to_log_file(param_test.fname_log, param_test.output, 'w')
        return update_param(param_test)

    param_test.output += o
    param_test.results['duration'] = time.time() - time_start

    # test integrity
    if param_test.test_integrity:
        param_test.output += '\n\n====================================================================================================\n' + 'INTEGRITY TESTING' + '\n====================================================================================================\n\n'  # copy command
        try:
            param_test = module_testing.test_integrity(param_test)
        except Exception as err:
            param_test.status = 2
            param_test.output += str(err)
            write_to_log_file(param_test.fname_log, param_test.output, 'w')
            return update_param(param_test)

    # manage stdout
    if param_test.redirect_stdout:
        sct.remove_handler(file_handler)
        write_to_log_file(param_test.fname_log, param_test.output, mode='r+', prepend=True)


    # go back to parent directory
    os.chdir(path_testing)

    return update_param(param_test)


def update_param(param):
    """
    Update field "results" in param class
    """
    for results_attr in param.results.columns:
        if hasattr(param, results_attr):
            param.results[results_attr] = getattr(param, results_attr)
    return param


# START PROGRAM
# ==========================================================================================
if __name__ == "__main__":
    sct.init_sct()
    # initialize parameters
    param = Param()
    # call main function
    main()
