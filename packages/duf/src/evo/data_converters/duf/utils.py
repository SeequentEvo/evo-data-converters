#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import clr

from evo.data_converters.duf.common import deswik_types as dw
from evo.data_converters.duf.common import DUFWrapper, InvalidDUFFileException


def is_duf(filepath: str) -> bool:
    """Returns `True` if the file appears to be a valid DUF file"""
    try:
        with DUFWrapper(filepath, None) as instance:
            instance.LoadSettings()
    except InvalidDUFFileException:
        return False
    else:
        return True


def nth_param_type(method, n: int):
    params = method.GetParameters()
    return params[n].ParameterType


def nth_constructor_param_type(csharp_type, n: int, n_constructor=0):
    constructors = clr.GetClrType(csharp_type).GetConstructors(dw.BindingFlags.Public | dw.BindingFlags.Instance)
    cons = constructors[n_constructor]
    return nth_param_type(cons, n)


def reflect_method(method):
    params = method.GetParameters()
    param_info = [f"{p.Name}: {p.ParameterType.Name}" for p in params]
    print(f"{method.Name}({', '.join(param_info)})")

    # Show more details about each parameter
    for p in params:
        print(f"  - {p.Name}: {p.ParameterType.FullName}")
        print(f"    Optional: {p.IsOptional}")
        try:
            if p.HasDefaultValue:
                print(f"    Default value: {p.DefaultValue}")
        except:  # noqa: E722  # Do not use bare `except`
            print("    Can't have default value (?)")

    try:
        [print(f"    Return type: {p.ReturnType}")]
    except:  # noqa: E722  # Do not use bare `except`
        print("    No return type")


def reflect_method_from_type(csharp_type, method_name: str):
    """
    Get the type by calling obj.GetType()
    """
    methods = [
        m for m in csharp_type.GetMethods(dw.BindingFlags.Instance | dw.BindingFlags.Public) if m.Name == method_name
    ]
    for m in methods:
        reflect_method(m)


def reflect_type(csharp_type):
    for method in csharp_type.GetMethods(dw.BindingFlags | dw.BindingFlags):
        reflect_method(method)


def reflect_constructors(csharp_type):
    constructors = clr.GetClrType(csharp_type).GetConstructors(dw.BindingFlags.Public | dw.BindingFlags.Instance)
    for c in constructors:
        reflect_method(c)


def reflect_nested_type(csharp_type, nested: str):
    clr.GetClrType(csharp_type).GetNestedType(nested)


def call_private(obj, method_name, *args):
    current_type = obj.GetType()

    # Find the first class in the hierarchy which declares the method. For whatever reason, it's not possible to
    # get the private method of the base class indirectly.
    while current_type is not None:
        method_info = current_type.GetMethod(
            method_name,
            dw.BindingFlags.NonPublic
            | dw.BindingFlags.Instance
            | dw.BindingFlags.DeclaredOnly,  # Only look at methods declared at this level
        )

        if method_info is not None:
            return method_info.Invoke(obj, args)

        current_type = current_type.BaseType

    raise ValueError(f"Method '{method_name}' not found in class hierarchy")


def get_private_field(obj, field_name: str):
    """
    Read a private instance field (member attribute) from a C# object.
    Walks base types because private members are not found via inheritance lookup.
    """
    current_type = obj.GetType()

    while current_type is not None:
        field_info = current_type.GetField(
            field_name,
            dw.BindingFlags.NonPublic
            | dw.BindingFlags.Instance
            | dw.BindingFlags.DeclaredOnly,
        )
        if field_info is not None:
            return field_info.GetValue(obj)

        current_type = current_type.BaseType

    raise ValueError(f"Field '{field_name}' not found in class hierarchy")
