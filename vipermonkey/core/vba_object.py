#!/usr/bin/env python
"""
ViperMonkey: VBA Grammar - Base class for all VBA objects

ViperMonkey is a specialized engine to parse, analyze and interpret Microsoft
VBA macros (Visual Basic for Applications), mainly for malware analysis.

Author: Philippe Lagadec - http://www.decalage.info
License: BSD, see source code or documentation

Project Repository:
https://github.com/decalage2/ViperMonkey
"""

# === LICENSE ==================================================================

# ViperMonkey is copyright (c) 2015-2016 Philippe Lagadec (http://www.decalage.info)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


# ------------------------------------------------------------------------------
# CHANGELOG:
# 2015-02-12 v0.01 PL: - first prototype
# 2015-2016        PL: - many updates
# 2016-06-11 v0.02 PL: - split vipermonkey into several modules

__version__ = '0.02'

# ------------------------------------------------------------------------------
# TODO:

# --- IMPORTS ------------------------------------------------------------------

import base64
from logger import log

class VBA_Object(object):
    """
    Base class for all VBA objects that can be evaluated.
    """

    # Upper bound for loop iterations. 0 or less means unlimited.
    loop_upper_bound = 10000000
    
    def __init__(self, original_str, location, tokens):
        """
        VBA_Object constructor, to be called as a parse action by a pyparsing parser

        :param original_str: original string matched by the parser
        :param location: location of the match
        :param tokens: tokens extracted by the parser
        :return: nothing
        """
        self.original_str = original_str
        self.location = location
        self.tokens = tokens

    def eval(self, context, params=None):
        """
        Evaluate the current value of the object.

        :param context: Context for the evaluation (local and global variables)
        :return: current value of the object
        """
        log.debug(self)
        # raise NotImplementedError

meta = None
        
def eval_arg(arg, context, treat_as_var_name=False):
    """
    evaluate a single argument if it is a VBA_Object, otherwise return its value
    """
    log.debug("try eval arg: %s" % arg)
    if isinstance(arg, VBA_Object):
        return arg.eval(context=context)
    else:
        log.debug("eval_arg: not a VBA_Object: %r" % arg)

        # Might this be a special type of variable lookup?
        if (isinstance(arg, str)):

            # Simple case first. Is this a variable?
            if (treat_as_var_name):
                try:
                    return context.get(arg)
                except:
                    
                    # No it is not. Try more complicated cases.
                    pass
            
            # This is a hack to get values saved in the .text field of objects.
            # To do this properly we need to save "FOO.text" as a variable and
            # return the value of "FOO.text" when getting "FOO.nodeTypedValue".
            if (".nodetypedvalue" in arg.lower()):
                try:
                    tmp = arg.lower().replace(".nodetypedvalue", ".text")
                    log.debug("eval_arg: Try to get as " + tmp + "...")
                    val = context.get(tmp)
    
                    # It looks like maybe this magically does base64 decode? Try that.
                    try:
                        log.debug("eval_arg: Try base64 decode of '" + val + "'...")
                        val_decode = base64.b64decode(str(val)).replace(chr(0), "")
                        log.debug("eval_arg: Base64 decode success: '" + val_decode + "'...")
                        return val_decode
                    except Exception as e:
                        log.debug("eval_arg: Base64 decode fail. " + str(e))
                        return val
                except KeyError:
                    log.debug("eval_arg: Not found as .text.")
                    pass

            # This is a hack to get values saved in the .rapt.Value field of objects.
            elif (".selecteditem" in arg.lower()):
                try:
                    tmp = arg.lower().replace(".selecteditem", ".rapt.value")
                    log.debug("eval_arg: Try to get as " + tmp + "...")
                    val = context.get(tmp)
                    return val

                except KeyError:
                    log.debug("eval_arg: Not found as .rapt.value.")
                    pass

            # Is this trying to access some VBA form variable?
            elif ("." in arg.lower()):

                # Try it as a form variable.
                tmp = arg.lower()
                try:
                    log.debug("eval_arg: Try to load as variable " + tmp + "...")
                    val = context.get(tmp)
                    return val

                except KeyError:
                    log.debug("eval_arg: Not found as variable")
                    pass

                # Try it as a function
                func_name = arg.lower()
                func_name = func_name[func_name.rindex(".")+1:]
                try:
                    log.debug("eval_arg: Try to run as function " + func_name + "...")
                    func = context.get(func_name)
                    return eval_arg(func, context, treat_as_var_name=True)

                except KeyError:
                    log.debug("eval_arg: Not found as function")

                except Exception as e:
                    log.debug("eval_arg: Failed. Not a function. " + str(e))

                # Are we trying to load some document meta data?
                if (tmp.startswith("activedocument.item(")):

                    # Try to pull the result from the document meta data.
                    prop = tmp.replace("activedocument.item(", "").replace(")", "").replace("'","").strip()

                    # Make sure we read in the metadata.
                    if (meta is None):
                        log.error("BuiltInDocumentProperties: Metadata not read.")
                        return ""
                
                    # See if we can find the metadata attribute.
                    if (not hasattr(meta, prop.lower())):
                        log.error("BuiltInDocumentProperties: Metadata field '" + prop + "' not found.")
                        return ""

                    # We have the attribute. Return it.
                    r = getattr(meta, prop.lower())
                    log.debug("BuiltInDocumentProperties: return %r -> %r" % (prop, r))
                    return r

                # Are we loading a document variable?
                if (tmp.startswith("activedocument.variables(")):

                    # ActiveDocument.Variables("ER0SNQAWT").Value
                    # Try to pull the result from the document variables.
                    var = tmp.replace("activedocument.variables(", "").\
                          replace(")", "").\
                          replace("'","").\
                          replace('"',"").\
                          replace('.value',"").\
                          strip()
                    val = context.get_doc_var(var)
                    if (val is not None):
                        return val

                # Are we loading a custom document property?
                if (tmp.startswith("activedocument.customdocumentproperties(")):

                    # ActiveDocument.CustomDocumentProperties("l3qDvt3B53wxeXu").Value
                    # Try to pull the result from the custom properties.
                    var = tmp.replace("activedocument.customdocumentproperties(", "").\
                          replace(")", "").\
                          replace("'","").\
                          replace('"',"").\
                          replace('.value',"").\
                          strip()
                    val = context.get_doc_var(var)
                    if (val is not None):
                        return val
                    
                # None of those worked. We can't find the data.
                #return "??"
                
        # The .text hack did not work.
        log.debug("eval_arg: return " + str(arg))
        return arg

def eval_args(args, context):
    """
    Evaluate a list of arguments if they are VBA_Objects, otherwise return their value as-is.
    Return the list of evaluated arguments.
    """
    return map(lambda arg: eval_arg(arg, context=context), args)

def coerce_to_str(obj):
    """
    Coerce a constant VBA object (integer, Null, etc) to a string.
    :param obj: VBA object
    :return: string
    """
    # in VBA, Null/None is equivalent to an empty string
    if ((obj is None) or (obj == "NULL")):
        return ''
    else:
        return str(obj)

def coerce_args_to_str(args):
    """
    Coerce a list of arguments to strings.
    Return the list of evaluated arguments.
    """
    # TODO: None should be converted to "", not "None"
    return [coerce_to_str(arg) for arg in args]
    # return map(lambda arg: str(arg), args)

def coerce_to_int(obj):
    """
    Coerce a constant VBA object (integer, Null, etc) to a int.
    :param obj: VBA object
    :return: int
    """
    # in VBA, Null/None is equivalent to 0
    if ((obj is None) or (obj == "NULL")):
        return 0
    else:
        return int(obj)

def coerce_args_to_int(args):
    """
    Coerce a list of arguments to ints.
    Return the list of evaluated arguments.
    """
    return [coerce_to_int(arg) for arg in args]

def coerce_args(orig_args):
    """
    Coerce all of the arguments to either str or int based on the most
    common arg type.
    """

    # Sanity check.
    if (len(orig_args) == 0):
        return orig_args

    # Convert args with None value to 'NULL'.
    args = []
    for arg in orig_args:
        if (arg is None):
            args.append("NULL")
        else:
            args.append(arg)
            
    # Find the 1st type in the arg list.
    first_type = None
    have_other_type = False
    for arg in args:

        # Skip NULL values since they can be int or str based on context.
        if (arg == "NULL"):
            continue
        if (isinstance(arg, str)):
            if (first_type is None):
                first_type = "str"
            continue
        elif (isinstance(arg, int)):
            if (first_type is None):
                first_type = "int"
            continue
        else:
            have_other_type = True
            break
        
    # Leave things alone if we have any non-int or str args.
    if (have_other_type):
        return args

    # Leave things alone if we cannot figure out the type to which to coerce.
    if (first_type is None):
        return args
    
    # Do conversion based on type of 1st arg in the list.
    if (first_type == "str"):

        # Replace unititialized values.
        new_args = []
        for arg in args:
            if (args == "NULL"):
                new_args.append('')
            else:
                new_args.append(arg)

        #log.debug("Coerce to str " + str(new_args))
        return coerce_args_to_str(new_args)

    else:

        # Replace unititialized values.
        new_args = []
        for arg in args:
            if (args == "NULL"):
                new_args.append(0)
            else:
                new_args.append(arg)

        #log.debug("Coerce to int " + str(new_args))
        return coerce_args_to_int(new_args)

def int_convert(arg):
    """
    Convert a VBA expression to an int, handling VBA NULL.
    """
    if (arg == "NULL"):
        return 0
    return int(arg)

def str_convert(arg):
    """
    Convert a VBA expression to an str, handling VBA NULL.
    """
    if (arg == "NULL"):
        return ''
    return str(arg)
