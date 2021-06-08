#
# Copyright (c) 2021 Seagate Technology LLC and/or its Affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.
#

import sys
from s3replicationcommon.aws_v4_signer import AWSV4Signer
from s3replicationcommon.s3_common import S3RequestState
from s3replicationcommon.timer import Timer


class S3AsyncGetObject:
    def __init__(self, session, bucket_name, object_name, object_size):
        """Initialise."""
        self._session = session
        self._logger = session.logger
        self._bucket_name = bucket_name
        self._object_name = object_name
        self._object_size = object_size

        self._http_status = None

        self._timer = Timer()
        self._state = S3RequestState.INITIALISED

    def get_state(self):
        """Returns current request state."""
        return self._state

    def get_execution_time(self):
        """Return total time for GET Object operation."""
        return self._timer.elapsed_time_ms()

    # yields data chunk for given size
    async def fetch(self, chunk_size):
        request_uri = AWSV4Signer.fmt_s3_request_uri(
            self._bucket_name, self._object_name)

        query_params = ""
        body = ""

        headers = AWSV4Signer(
            self._session.endpoint,
            self._session.service_name,
            self._session.region,
            self._session.access_key,
            self._session.secret_key).prepare_signed_header(
            'GET',
            request_uri,
            query_params,
            body)

        if (headers['Authorization'] is None):
            self._logger.error("Failed to generate v4 signature")
            sys.exit(-1)

        # Maximum to fetch so we dont keep reading indefinitely.
        total_to_fetch = self._object_size

        self._logger.info('GET on {}'.format(
            self._session.endpoint + request_uri))
        self._timer.start()
        async with self._session.get_client_session().get(
                self._session.endpoint + request_uri, headers=headers) as resp:
            self._state = S3RequestState.RUNNING
            while True:
                # If abort requested, stop the loop and return.
                if self._state == S3RequestState.ABORTED:
                    self._logger.debug(
                        "Aborted after reading %d bytes"
                        "for object size of %d",
                        (self._object_size - total_to_fetch,
                         self._object_size))
                    break

                data_chunk = await resp.content.read(chunk_size)
                if not data_chunk:
                    break
                self._logger.debug(
                    "Received data_chunk of size {} bytes.".format(
                        len(data_chunk)))
                yield data_chunk

                total_to_fetch = total_to_fetch - len(data_chunk)
                if total_to_fetch == 0:
                    # Completed reading all expected data.
                    self._state = S3RequestState.COMPLETED
                    break
                elif total_to_fetch < 0:
                    self._state = S3RequestState.FAILED
                    self._logger.error(
                        "Received %d more bytes than"
                        "expected object size of %d",
                        (total_to_fetch * -1,
                         self._object_size))
            # end of While True
            self._timer.stop()

            if self._state != S3RequestState.ABORTED:
                self._http_status = resp.status
                self._logger.info(
                    'GET Object completed with http status: {}'.format(
                        resp.status))

                if total_to_fetch > 0:
                    self._state = S3RequestState.FAILED
                    self._logger.error(
                        "Received partial object. Expected object size (%d), "
                        "Actual received size (%d)",
                        self._object_size,
                        self._object_size - total_to_fetch)

    def pause(self):
        self._state = S3RequestState.PAUSED
        # XXX Take real pause action

    def resume(self):
        self._state = S3RequestState.PAUSED
        # XXX Take real resume action

    def abort(self):
        self._state = S3RequestState.ABORTED
        # XXX Take abort pause action