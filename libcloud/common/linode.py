# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

try:
    import simplejson as json
except ImportError:
    import json

from libcloud.common.base import ConnectionKey, Response
from libcloud.common.types import InvalidCredsError, MalformedResponseError

__all__ = [
    'API_HOST',
    'API_ROOT',
    'LinodeException',
    'LinodeResponse',
    'LinodeConnection'
]

# Endpoint for the Linode API
API_HOST = 'api.linode.com'
API_ROOT = '/'

# Constants that map a RAM figure to a PlanID (updated 6/28/10)
LINODE_PLAN_IDS = {512:'1',
                   768:'2',
                  1024:'3',
                  1536:'4',
                  2048:'5',
                  4096:'6',
                  8192:'7',
                 12288:'8',
                 16384:'9',
                 20480:'10'}


class LinodeException(Exception):
    """Error originating from the Linode API

    This class wraps a Linode API error, a list of which is available in the
    API documentation.  All Linode API errors are a numeric code and a
    human-readable description.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        self.args = (code, message)

    def __str__(self):
        return "(%u) %s" % (self.code, self.message)

    def __repr__(self):
        return "<LinodeException code %u '%s'>" % (self.code, self.message)


class LinodeResponse(Response):
    """Linode API response

    Wraps the HTTP response returned by the Linode API, which should be JSON in
    this structure:

       {
         "ERRORARRAY": [ ... ],
         "DATA": [ ... ],
         "ACTION": " ... "
       }

    libcloud does not take advantage of batching, so a response will always
    reflect the above format.  A few weird quirks are caught here as well."""
    def __init__(self, response):
        """Instantiate a LinodeResponse from the HTTP response

        @keyword response: The raw response returned by urllib
        @return: parsed L{LinodeResponse}"""
        self.body = response.read()
        self.status = response.status
        self.headers = dict(response.getheaders())
        self.error = response.reason
        self.invalid = LinodeException(0xFF,
                                       "Invalid JSON received from server")

        # Move parse_body() to here;  we can't be sure of failure until we've
        # parsed the body into JSON.
        self.objects, self.errors = self.parse_body()
        if not self.success():
            # Raise the first error, as there will usually only be one
            raise self.errors[0]

    def parse_body(self):
        """Parse the body of the response into JSON objects

        If the response chokes the parser, action and data will be returned as
        None and errorarray will indicate an invalid JSON exception.

        @return: C{list} of objects and C{list} of errors"""
        try:
            js = json.loads(self.body)
        except:
            raise MalformedResponseError("Failed to parse JSON", body=self.body)

        try:
            if isinstance(js, dict):
                # solitary response - promote to list
                js = [js]
            ret = []
            errs = []
            for obj in js:
                if ("DATA" not in obj or "ERRORARRAY" not in obj
                    or "ACTION" not in obj):
                    ret.append(None)
                    errs.append(self.invalid)
                    continue
                ret.append(obj["DATA"])
                errs.extend(self._make_excp(e) for e in obj["ERRORARRAY"])
            return (ret, errs)
        except:
            return (None, [self.invalid])

    def success(self):
        """Check the response for success

        The way we determine success is by the presence of an error in
        ERRORARRAY.  If one is there, we assume the whole request failed.

        @return: C{bool} indicating a successful request"""
        return len(self.errors) == 0

    def _make_excp(self, error):
        """Convert an API error to a LinodeException instance

        @keyword error: JSON object containing C{ERRORCODE} and C{ERRORMESSAGE}
        @type error: dict"""
        if "ERRORCODE" not in error or "ERRORMESSAGE" not in error:
            return None
        if error["ERRORCODE"] == 4:
            return InvalidCredsError(error["ERRORMESSAGE"])
        return LinodeException(error["ERRORCODE"], error["ERRORMESSAGE"])


class LinodeConnection(ConnectionKey):
    """A connection to the Linode API

    Wraps SSL connections to the Linode API, automagically injecting the
    parameters that the API needs for each request."""
    host = API_HOST
    responseCls = LinodeResponse

    def add_default_params(self, params):
        """Add parameters that are necessary for every request

        This method adds C{api_key} and C{api_responseFormat} to the request."""
        params["api_key"] = self.key
        # Be explicit about this in case the default changes.
        params["api_responseFormat"] = "json"
        return params