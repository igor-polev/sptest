#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Console command execution time measurement script.
Designed for Python 3.6.8 compatibility. Only standard libs are used.

@author: IGOR POLEV
"""

from sys        import exit, argv
from getopt     import getopt, GetoptError
from os.path    import isfile
from contextlib import closing
from threading  import Thread, local
from time       import sleep
from json       import loads as json_loads
from datetime   import datetime, timedelta, MINYEAR, MAXYEAR
from subprocess import run as subprocess_run
from subprocess import DEVNULL

_DEFAULT_RUNS  = 8
_DEFAULT_PAUSE = 5

help_text = '''
Run console command and measure its execution time.
Usage:
    python3 sptest.py [<parameters> | <filename>]

Parameters can be provided using command line or JSON file. JSON is a priority.

Parameters:
    -c COMMAND : command to execute, mandatory parameter;
                 JSON key name - COMMAND
    -p         : run commands in parallel, by default commands are executed
                 sequentially;
                 JSON key name - PARALLEL, presence of this key in JSON file
                 turns parallel mode on, value of this key is ignored
    -n TIMES   : number of parallel copies in parallel mode or number of
                 repeated runs in sequential mode, {def_runs} by default;
                 JSON key name - TIMES
    -w SECONDS : pause in seconds - between commands start in parallel mode or
                 between each command run in sequential mode, {def_pause} by
                 default;
                 JSON key name - SECONDS
    -h, --help : display usage info, not used in JSON

All parameters but -c (COMMAND) are optional. If JSON file is provided and decoded
successfully, parameters from JSON are used and command line parameters are
ignored. Overwise command line parameters are used.

Attention! The validity of COMMAND is not checked. Be careful not to run
invalid command multiple times!

Examples of usage:
    python3 sptest.py -p -c 'ls -la' -n 5
    ./sptest.py test.json

JSON example:
{op}
    "COMMAND": "ls -la",
    "SECONDS": 1,
    "PARALLEL": "any_value"
{cl}
'''.format(
    def_runs  = _DEFAULT_RUNS,
    def_pause = _DEFAULT_PAUSE,
    op = '{', cl = '}' # Dumb params to insert curly brackets into f-string
)

class SPscript:

    def __init__(self, cmdl_params):

        self.mode_prl = False
        self.command  = ""
        self.runs     = _DEFAULT_RUNS
        self.pause    = _DEFAULT_PAUSE

        try:
            opts, args = getopt(cmdl_params, "c:n:w:ph", ["help"])
            if not opts and not args:
                self.no_command()
            if args: # JSON filename provided
                filename = args[0]
                if not isfile(filename):
                    print("File '{}' not found.".format(filename))
                    exit(2)
                try:
                    with closing(open(filename, 'r')) as file:
                        json_text = file.read()
                except Exception as err:
                    print("Error while reading file '{}':".format(filename), err, sep='\n')
                    exit(2)
                try:
                    json_data = json_loads(json_text)
                except Exception as err:
                    print("Error while parsing JSON data from file '{}':".format(filename), json_text, err, sep='\n')
                    exit(2)
                opts = list(json_data.items())
            for opt, value in opts:
                if   opt == '-c' or opt.upper() == 'COMMAND'  : self.command  = value
                elif opt == '-n' or opt.upper() == 'TIMES'    : self.runs     = int(value)
                elif opt == '-w' or opt.upper() == 'SECONDS'  : self.pause    = int(value)
                elif opt == '-p' or opt.upper() == 'PARALLEL' : self.mode_prl = True
                elif opt in ('-h', '--help'):
                    print(help_text)
                    exit(0)
                if self.runs < 1 or self.pause < 0:
                    raise ValueError
        except ValueError as err:
            print("Values of -n (TIMES) and/or -w (SECONDS) parameters do not look like suitable integers.", err, sep='\n')
            exit(2)
        except GetoptError as err:
            print(err, help_text, sep='\n')
            exit(2)
        if not self.command:
            self.no_command()
        
        TIME_NONE = datetime(year=MINYEAR, month=1, day=1)
        self.timings = [
            {
                'e_code' : 0,
                'start'  : TIME_NONE,
                'finish' : TIME_NONE,
                'time'   : timedelta()
            }
            for i in range(self.runs)
        ]

    def no_command(self):
        print("Command to run is not provided, see help below.", help_text, sep='\n')
        exit(2)

    def run_command(self, iteration):
        data = local()
        data.start = datetime.now()
        data.cmd_result = subprocess_run(
            self.command,
            shell=True,
            stdout=DEVNULL, # to prevent memory overrun in case of huge output
            stderr=DEVNULL  # to stop console output completely
        )
        data.finish = datetime.now()
        self.timings[iteration]['e_code'] = data.cmd_result.returncode
        self.timings[iteration]['start']  = data.start
        self.timings[iteration]['finish'] = data.finish
        self.timings[iteration]['time']   = data.finish - data.start

    def execute(self):

        print("Executing command '{cmd}' {n} times with {p} sec pause".format(
            cmd = self.command,
            n   = self.runs,
            p   = self.pause
        ), end=' ')

        if self.mode_prl:
            print("in parallel mode:")
            threads = [
                Thread(target=self.run_command, args=(i,))
                for i in range(self.runs)
            ]
        else:
            print("in sequential mode:")
        for i in range(self.runs):
            print("starting iteration {}...".format(i + 1), end=' ', flush=True)
            if self.mode_prl:
                threads[i].start()
                print("started")
            else:
                self.run_command(i)
                print("done in", self.timings[i]['time'])
            if i + 1 < self.runs: # No need for sleep on last iteration
                sleep(self.pause)
        if self.mode_prl:
            print("Waiting for threads to finish...", end=' ', flush=True)
            for th in threads: th.join()
            print("done")

        # Results processing
        min_start  = datetime(year=MAXYEAR, month=12, day=31)
        max_finish = datetime(year=MINYEAR, month=1,  day=1)
        sum_time   = timedelta()
        min_time   = timedelta.max
        max_time   = timedelta.min
        error_cnt  = 0
        for timing in self.timings:
            if timing['e_code'] != 0         : error_cnt += 1
            if timing['start']  < min_start  : min_start  = timing['start']
            if timing['finish'] > max_finish : max_finish = timing['finish']
            if timing['time']   < min_time   : min_time   = timing['time']
            if timing['time']   > max_time   : max_time   = timing['time']
            sum_time += timing['time']
        total_time = max_finish - min_start
        print("Total time spent ...........", total_time)
        print("Fastest iteration ..........", min_time)
        print("Slowest iteration ..........", max_time)
        print("Average iteration ..........", sum_time / float(self.runs))
        times = sorted(list(map(lambda t: t['time'], self.timings)))
        mid_pos = self.runs // 2
        # Hocus-pocus with ~ operator for median calculation
        print("Median iteration ...........", (times[mid_pos] + times[~mid_pos]) * 0.5)
        if error_cnt:
            print("Attention! {} iteration(s) finished with non-zero exit code!".format(error_cnt))

if __name__ == "__main__":
    try:
        script = SPscript(argv[1:])
        script.execute()
    except Exception as err:
        print("\nUnhandled exception!\n", err, sep='\n')
        exit(1)
    exit(0)