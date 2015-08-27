"""1 to 1 mappings of hangups legacy enums, but as standard classes"""
import inspect, logging, re, sys

import hangups


logger = logging.getLogger(__name__) # logger is mostly useless, since initialised before config


_current_module = sys.modules[__name__]
_current_attrs = dir(_current_module)


def _remap(name):
    module_attribute_name = name[0]
    hangups_pbname = name[1]

    if module_attribute_name in _current_attrs:
        return

    object = type('test', (), {})()

    if "schemas" in dir(hangups):
        enum = getattr(hangups.schemas, module_attribute_name)
        filtered = enum.__members__
    elif "hangouts_pb2" in dir(hangups):
        # XXX: yes im totally aware of how hacky this is
        # read in the new pb-variables and remap them to the original enum names
        filtered = {}
        everything = inspect.getmembers(hangups.hangouts_pb2)
        for member_name, member_data in everything:
            if member_name.startswith(hangups_pbname):
                _name = member_name[len(hangups_pbname)+1:]
                _value = getattr(hangups.hangouts_pb2, member_name)
                filtered[_name] = _value

    if len(filtered) == 0:
        print("nothing to map!")

    for _name, _value in filtered.items():
        print("{}: attribute {} to {}".format(module_attribute_name, _name, _value))
        setattr(object, _name, _value)

    setattr(_current_module, module_attribute_name, object)


for mapping in [("TypingStatus", "TYPING_TYPE"),
                ("FocusStatus", "FOCUS_TYPE"),
                ("FocusDevice", "FOCUS_DEVICE"),
                ("ConversationType", "CONVERSATION_TYPE"),
                ("ClientConversationView", "CONVERSATION_VIEW"),
                ("ClientNotificationLevel", "NOTIFICATION_LEVEL"),
                ("ClientConversationStatus", "CONVERSATION_STATUS"),
                ("SegmentType", "SEGMENT_TYPE"),
                ("MembershipChangeType", "MEMBERSHIP_CHANGE_TYPE"),
                ("ClientHangoutEventType", "HANGOUTS_EVENT_TYPE"),
                ("OffTheRecordStatus", "OFF_THE_RECORD_STATUS"),
                ("ClientOffTheRecordToggle", "OFF_THE_RECORD_TOGGLE"),
                ("ActiveClientState", "ACTIVE_CLIENT_STATE")]:

    _remap(mapping)
