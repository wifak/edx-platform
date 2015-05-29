"""
Get call stacks of Model Class
in three cases-
1. QuerySet API
2. save()
3. delete()

classes:
Globals - contains global stack_book dictionary , also regular expression filters
CallStackManager -  stores all stacks in global dictionary and logs

How to use-
1. Import following in the file where class to be track resides
    from openedx.core.lib.call_stack_manager import CallStackManager
2. Override objects of default manager by writing following in any model class which you want to track-
    objects = CallStackManager()

Note -
1.Format for stack_book
{
    "modelclass1":
        [[(frame 1),(frame 2)],
         [(frame 11),(frame21)]]
    "modelclass2":
        [[(frame 3),(frame 4)],
         [(frame 6),(frame 5)]]

}
where frame is a tuple of
(file path, Line Number, Context)
"""

import logging
import traceback
import re
import threading

from django.db.models import Manager


log = logging.getLogger(__name__)


class Globals(threading.local):
    """
    stores necessary global data structures for Call Stacks and runs a method necessary for
    """
    # dictionary which stores call stacks.
    # { "ModelClasses" : [ListOfFrames]}
    # Frames - ('FilePath','LineNumber','Context')
    # ex. {"<class 'courseware.models.StudentModule'>" : [[(file,line number,context),(---,---,---)],
    #                                                     [(file,line number,context),(---,---,---)]]}
    stack_book = {}

    # filter to trickle down call stacks.
    exclude = ['^.*python2.7.*$', '^.*call_stack_manager.*$']
    regular_expressions = [re.compile(x) for x in exclude]

# Instantiate Globals Class.
_m = Globals()


class CallStackManager (Manager):
    """
    gets call stacks of model classes
    """
    def __init__(self):
        super(CallStackManager, self).__init__()

    def get_call_stack(self):
        """
        stores customised call stacks in global dictionary `stack_book`, and logs it.
        """
        # get name of current model class
        current_model = str(self.model)
        current_model = current_model[current_model.find('\'')+1: current_model.rfind('\'')]

        # holds temporary callstack
        temp_call_stack = []

        for line in traceback.format_stack():
            line = line.replace("\n", "")
            temp_call_stack.append(line.split(',')[0].strip() + "+" + line.split(',')[1].strip() + "+" +
                                   line.split(',')[2].strip())

        # filtering w.r.t. regular_expressions
        temp_call_stack = [frame for frame in temp_call_stack if not(len(filter(lambda re: re.match(frame),
                                                                                _m.regular_expressions)))]
        # convert frame in tuple format
        temp_call_stack = map(lambda x: tuple(x.split("+")), temp_call_stack)

        # store in the format ('file','line number','context')
        temp_call_stack = map(lambda x: (x[0][6:-1], x[1][6:], x[2][3:]), temp_call_stack)

        # avoid duplication.
        if current_model in _m.stack_book.keys():
            if temp_call_stack not in _m.stack_book[current_model]:
                _m.stack_book.setdefault(current_model, []).append(temp_call_stack)
                log.info("logging new call in global stack book")
                log.info(_m.stack_book)
        else:
            _m.stack_book.setdefault(current_model, []).append(temp_call_stack)
            log.info("logging new model class in global stack book")
            log.info(_m.stack_book)

    def get_query_set(self):
        """
        overriding the default queryset API methods
        """
        self.get_call_stack()
        return super(CallStackManager, self).get_query_set()

    def save(self, *args, **kwargs):
        """
        Logs before save and overrides respective model API save()
        """
        self.get_call_stack()
        return super(CallStackManager, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Logs before delete and overrides respective model API delete()
        """
        self.get_call_stack()
        return super(CallStackManager, self).save(*args, **kwargs)
