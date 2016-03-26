# standard library
import datetime

# 3rd party libraries

# project libraries
import core

class Computers(core.CoreDict):
  def __init__(self, manager=None):
    core.CoreDict.__init__(self)
    self._exempt_from_find.append('groups')
    self.manager = manager
    self.log = self.manager.log if self.manager else None

  def get(self, detail_level='HIGH', computer_id=None, computer_group_id=None, security_profile_id=None, computer_name=None, external_id=None, external_group_id=None):
    """
    Get all or a filtered set of computers from Deep Security

    Can filter by:
      computer_id
      computer_group_id
      security_profile_id
      computer_name (specific or starts with using name*)
      external_id
      external_group_id

    If multiple filters are requested, only one is applied. The priority is;
      external_id
      external_group_id
      computer_name
      computer_id
      computer_group_id
      security_profile_id

    detail_level can be set to one of ['HIGH', 'MEDIUM', 'LOW']
    """
    # make sure we have a valid detail level
    detail_level = detail_level.upper()
    if not detail_level in ['HIGH', 'MEDIUM', 'LOW']: detail_level = 'HIGH'

    call = None
    if external_id and external_group_id:
      call = self.manager._get_request_format(call='hostDetailRetrieveByExternal')
      if external_id:
        call['data'] = {
          'externalFilter': {
            'hostExternalID': external_id,
            'hostGroupExternalID': None,
          },
          'hostDetailLevel': detail_level
        }
      elif external_group_id:
        call['data'] = {
          'externalFilter': {
            'hostExternalID': None,
            'hostGroupExternalID': external_group_id,
          },
          'hostDetailLevel': detail_level
        }
    if computer_name:
      if computer_name.endswith('*'):
        call = self.manager._get_request_format(call='hostDetailRetrieveByNameStartsWith')
        call['data'] = {
          'hostname': computer_name,
          'hostDetailLevel': detail_level
          }
      else:
        call = self.manager._get_request_format(call='hostDetailRetrieveByName')
        call['data'] = {
          'startsWithHostname': computer_name.rstrip('*'),
          'hostDetailLevel': detail_level
          }
    else:
      # get with no arguments = hostRetrieve() with ALL_HOSTS
      call = self.manager._get_request_format(call='hostDetailRetrieve')
      call['data'] = {
          'hostFilter': {
            'hostGroupID': None,
            'hostID': None,
            'securityProfileID': None,
            'type': 'ALL_HOSTS',
          },
          'hostDetailLevel': detail_level
        }

    response = self.manager._request(call)
    
    if response and response['status'] == 200:
      if not type(response['data']) == type([]): response['data'] = [response['data']]
      for computer in response['data']:
        computer_obj = Computer(self.manager, computer, self.log)
        if computer_obj:
          self[computer_obj.ID] = computer_obj
          # add this computer to any appropriate groups on the Manager()
          if 'hostGroupID' in dir(computer_obj) and computer_obj.hostGroupID:
            if self.manager.computer_groups and self.manager.computer_groups.has_key(computer_obj.hostGroupID):
              self.manager.computer_groups[computer_obj.hostGroupID].computers[computer_obj.ID] = computer_obj

    return len(self)

class ComputerGroups(core.CoreDict):
  def __init__(self, manager=None):
    core.CoreDict.__init__(self)
    self.manager = manager
    self.log = self.manager.log if self.manager else None

  def get(self, name=None, group_id=None):
    """
    Get all or a filtered set of computer groups from Deep Security

    If a name or group_id is specified, will only retrieve the 
    computer groups matching the name or group_id.

    If both are specified, name takes priority
    """
    call = None
    if name or group_id:
      # filtered call
      if name:
        call = self.manager._get_request_format(call='hostGroupRetrieveByName')
        call['data'] = {
          'Name': name
          }
      elif group_id:
        call = self.manager._get_request_format(call='hostGroupRetrieve')
        call['data'] = {
          'ID': '{}'.format(group_id)
          }
    else:
      call = self.manager._get_request_format(call='hostGroupRetrieveAll')

    response = self.manager._request(call)
    if response and response['status'] == 200:
      self.clear() # empty the current groups
      if not type(response['data']) == type([]): response['data'] = [response['data']]
      for group in response['data']:
        computer_group_obj = ComputerGroup(self.manager, group, self.log)
        if computer_group_obj:
          self[computer_group_obj.ID] = computer_group_obj

    return len(self)

class Computer(core.CoreObject):
  def __init__(self, manager=None, api_response=None, log_func=None):
    self.manager = manager
    if api_response: self._set_properties(api_response, log_func)

  def send_events(self):
    """
    Send the latest set of events to this computer's Manager
    """
    return self.manager.request_events_from_computer(self.ID)

class ComputerGroup(core.CoreObject):
  def __init__(self, manager=None, api_response=None, log_func=None):
    self.manager = manager
    if api_response: self._set_properties(api_response, log_func)
    self.computers = core.CoreDict()

  def send_events(self):
    """
    Send the latest set of events for all computers in this group
    """
    results = {}
    for computer_id, computer in self.computers.items():
      if 'send_events' in dir(computer):
        results[computer_id] = computer.send_events()

    return results