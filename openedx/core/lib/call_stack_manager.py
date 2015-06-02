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
1. Import following in the file where class to be tracked resides
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
import collections

from django.db.models import Manager
from django.db import models


log = logging.getLogger(__name__)


# Module Level variables
# dictionary which stores call stacks.
# { "ModelClasses" : [ListOfFrames]}
# Frames - ('FilePath','LineNumber','Context')
# ex. {"<class 'courseware.models.StudentModule'>" : [[(file,line number,context),(---,---,---)],
#                                                     [(file,line number,context),(---,---,---)]]}
stack_book = {}
stack_book = collections.defaultdict(list)

# filter to trickle down call stacks.
exclude = ['^.*python2.7.*$', '^.*call_stack_manager.*$']
regular_expressions = [re.compile(x) for x in exclude]


class CallStackManager(Manager):
    """
    gets call stacks of model classes
    """
    def capture_call_stack(self):
        """
        stores customised call stacks in global dictionary `stack_book`, and logs it.
        """
        # get name of current model class
        current_model = str(self.model)

        # holds temporary callstack
        temp_call_stack = [(line.split(',')[0].strip().replace("\n", "")[6:-1],
                            line.split(',')[1].strip().replace("\n", "")[6:],
                            line.split(',')[2].strip().replace("\n", "")[3:])
                           for line in traceback.format_stack()
                           if not any(reg.match(line.replace("\n", "")) for reg in regular_expressions)]

        # avoid duplication.
        if temp_call_stack not in stack_book[current_model]:
            stack_book[current_model].append(temp_call_stack)
            log.info("logging new call in global stack book")
            log.info(stack_book)

    def get_query_set(self):
        """
        overriding the default queryset API methods
        """
        self.capture_call_stack()
        return super(CallStackManager, self).get_query_set()

    def save(self, *args, **kwargs):
        """
        Logs before save and overrides respective model API save()
        """
        self.capture_call_stack()
        return super(CallStackManager, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Logs before delete and overrides respective model API delete()
        """
        self.capture_call_stack()
        return super(CallStackManager, self).save(*args, **kwargs)
