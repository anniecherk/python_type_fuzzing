"""
GrIFT is fuzzy typing is a python type fuzzer which can be used to type check
python modules, files, and single functions.
"""

from typing import Any, Callable, Dict, List, Optional, TypeVar
import os
import sys
import json
from collections import defaultdict
from inspect import signature

from instances import *
from itertools import product, repeat

import click


# Set the environment codec variables so that click is callable from python3
if 'linux' in sys.platform:
    os.environ['LC_AL'] = "C.UTF-8"
    os.environ['LANG'] = "C.UTF-8"
else:
    os.environ['LC_AL'] = "en_US.utf-8"
    os.environ['LANG'] = "en_US.utf-8"


# Define generic type variables
A = TypeVar("A")
B = TypeVar("B")
CLS = TypeVar("Class")


@click.group()
def main():
    pass


    """
JSON SPEC

    [
        {
        function_to_type : addOnes
        results :
            {
                successes:
                    {
                        string : ["a", "b"]
                        int : [1, -2]
                    }
                failures:
                    {
                        string : ["-a", "*b"]
                        int : [-1, 2]
                    }
            }
    ]
    """


def print_thin_bar(width):
    print("─" * width)


def print_thick_bar(width):
    print("━" * width)


def default_print(json_obj, print_failures: bool=False):
    for func in json_obj:
        indent = 40
        width = 80
        print_thick_bar(width)

        print(" "*(indent-2) + "TESTED\n" + str(func["function_to_type"]))
        results = func["results"]

        print("\n" + " "*(indent-3) + "SUCCESSES")

        print("─"*indent + "┬" + "─"*(width-indent-1))
        print(" "*((indent//2)-2) + "type" + " "*((indent//2)-2) + "│" + "   " + "instance")
        print("─"*indent + "┼" + "─" * (width - indent - 1))

        for types, insts in results["successes"].items():
            print(types.rjust(indent-1) + " │ ", insts[0])

        if print_failures:

            print("\n\n" + " "*(indent-3) + "FAILURES")

            print("─"*indent + "┬" + "─"*(width-indent-1))
            print(" "*((indent//2)-2) + "type" + " "*((indent//2)-2) + "│" + "   " + "instance")
            print("─"*indent + "┼" + "─" * (width - indent - 1))

            for types, insts in results["failures"].items():
                print(types.rjust(indent-1) + " │ ", insts[0])
            print_thick_bar(width)


def show_results(typeAccum):
    for (typeAnnotation, inst) in typeAccum:
        print(typeAnnotation + "│", inst)


@main.command("fuzz")
@click.argument("file-path")
@click.argument("function-name")
@click.option("--print-failures/--no-print-failures", default=False)
def fuzz(file_path: str, function_name: str, print_failures: bool):
    result_json = list()
    result_json.append(run_fuzzer(file_path, function_name))
    default_print(result_json, print_failures=print_failures)


def flat_func_app(func: Callable[..., B], args: List[A]) -> B:
    """Applys a function to a list of arguments

    Args:
        func: A function which we want to apply
        args: The list of arguments

    Returns:
        The output of calling func on args
    """
    return func(*args)


def class_func_app(class_instance: CLS,
                   func: Callable[..., B],
                   func_args: List[A]
                   ) -> B:
    """

    Args:
        class_instance: An instance of a class
        func: The class function we want to evaluate
        func_args: The arguments to the function

    Returns:
        The class function func applied to the arguments func_args
    """
    # call the function with the instance
    return func(*([class_instance] + func_args))


def get_function(file_name: str, function_name: str) -> Callable[..., Any]:
    """Gets the callable function with name function_name

    Args:
        file_name: The file where our function is defined
        function_name: The name of the function we'd like to load
            programatically

    Returns:
        The callable function.
    """
    funcs = function_name.split(".")
    if len(funcs) == 1:
        return getattr(__import__(file_name), funcs[0])
    else:
        return getattr(getattr(__import__(file_name), funcs[0]), funcs[1])


def fuzz_example(file_name: str,
                 function_name: str,
                 class_instance: Optional[Any]=None
                 ) -> Dict[Any, Any]:
    """Type fuzzes a single example

    Args:
        file_name: The file name where the function we'd like to fuzz is located
        function_name: The name of the function we'd like to fuzz
        class_instance: The instance of the class this function is a member of
            if any.

    Returns:
        A JSON object describing which combinations of type instances were
        successful.
    """
    # Import the method we are interested in
    func = get_function(file_name, function_name)

    # Examine the imported function for annotations and parameters
    num_params = len(signature(func).parameters)
    # annotations = func.__annotations__

    instances = get_instances()

    # instances = get_dummy()
    all_inputs = list(product(*repeat(instances, num_params)))

    result_dict = {"function_to_type": function_name,
                   "results": {"successes": defaultdict(list),
                               "failures": defaultdict(list)
                               }
                   }

    for input_args in all_inputs:
        types_only = [x[0] for x in input_args]
        args_only = [x[1] for x in input_args]

        try:
            if class_instance is None:
                flat_func_app(func, args_only)
                result_dict['results']['successes'][str(types_only)[1:-1]].append(args_only)
            else:
                class_func_app(class_instance, func, args_only)
                result_dict['results']['successes'][str(types_only)[1:-1]].append(args_only)

        except:
            result_dict['results']['failures'][str(types_only)[1:-1]].append(args_only)

    return result_dict


def run_fuzzer(file_path: str, function_name: str) -> Dict[Any, Any]:
    path = os.path.split(file_path)
    file_name = path[-1][:-3]
    path_str = os.path.join(*path[:-1])
    sys.path.append(path_str)

    # Check function name to see if it is nested in a class
    funcs = function_name.split(".")

    # NOTE: The maximum class depth is 2.
    if len(funcs) == 2:
        # Step 1, fuzz the constructor
        # Get the name of the class
        constructor_name = funcs[0]

        # Fuzz the class constructor so we can instantiate it
        valid_constructor_calls_json = fuzz_example(file_name, constructor_name)

        # Get valid constructor types and args
        good_constr_args = list(valid_constructor_calls_json["results"]["successes"].values())

        # TODO: run over all (?) successful class instances

        # Instantiate the class
        class_constr = get_function(file_name, constructor_name)
        class_instance = class_constr(*(good_constr_args[0][0]))

        # Fuzz the function using single instance of the class
        return fuzz_example(file_name, function_name, class_instance)

    elif len(funcs) == 1:
        return fuzz_example(file_name, function_name)
    else:
        raise ValueError(f"{function_name} must either be the name of a function or a [single nested] class method")


if __name__ == "__main__":
    main()
