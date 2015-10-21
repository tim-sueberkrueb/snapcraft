# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import snapcraft
import urllib.request
import os.path
from subprocess import check_call, check_output, CalledProcessError
import json
from pprint import pprint

class AWSIoTPlugin(snapcraft.BasePlugin):
    # Should be updated with the final AWS URL
    AWSCERTURL="https://t71u6yob51.execute-api.us-east-1.amazonaws.com/beta"

    @classmethod
    def schema(cls):
        return {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'properties': {
                'generatekeys': {
                    'type': 'boolean',
                    'default': True
                },
                'policydocument': {
                    'type': 'string',
                    'default': ''
                },
                'policyname': {
                    'type': 'string',
                    'default': 'PubSubToAnyTopic'
                },
                'thing': {
                    'type': 'string',
                },
            },
            'required': ['thing']
        }

    def __init__(self, name, options):
        super().__init__(name, options)
        # True if new keys should be generated by Amazon, otherwise generate keys locally
        self.generatekeys = options.generatekeys      
        # Which policy document should be used. Optional. Allow all IoT will be used if not specified
        self.policydocument = options.policydocument
        # Which policy name should be used. Optional. 'PubSubToAnyTopic' will be used if not specified
        self.policyname = options.policyname
        # The thing to create
        self.thing = options.thing
        
    def pull(self):
        return True

    def build(self):
        # Make the certs directory if it does not exist
        if not os.path.exists('certs'):
            os.makedirs('certs')
        # What should we do with certificates?
        if self.generatekeys:
            # generate new keys
            check_call('aws iot --endpoint %s create-keys-and-certificate --set-as-active > certs/certs.json' % self.AWSCERTURL, shell=True)
            #separate into different files
            with open('certs/certs.json') as data_file:    
                self.data = json.load(data_file)
            text_file = open("certs/cert.pem", "w")
            text_file.write(self.data["certificatePem"])
            text_file.close()
            text_file = open("certs/privateKey.pem", "w")
            text_file.write(self.data["keyPair"]["PrivateKey"])
            text_file.close()
            text_file = open("certs/publicKey.pem", "w")
            text_file.write(self.data["keyPair"]["PublicKey"])
            text_file.close()            
        else:
            # generate private key
            check_output('openssl genrsa -out certs/privateKey.pem 2048',shell=True)
            check_output('openssl req -new -key certs/privateKey.pem -out certs/cert.csr',shell=True)	
            # generate new keys based on a csr
            #TODO: test the rest of the methods because it always gives an invalid CSR request
            check_output('aws iot --endpoint {0} create-certificate-from-csr --certificate-signing-request certs/cert.csr --set-as-active > certresponse.txt'.format(self.AWSCERTURL), shell=True)
            with open('certresponse.txt') as data_file:    
                self.data = json.load(data_file)
            check_call('aws iot --endpoint {0} describe-certificate --certificate-id {1} --output text --query certificateDescription.certificatePem > certs/cert.pem'.format(self.AWSCERTURL,self.data["arn"].split(":cert/")[1]), shell=True)
            check_output('rm certresponse.txt', shell=True)
        #Get the root certificate
        self.filename = urllib.request.urlretrieve(
            'https://www.symantec.com/content/en/us/enterprise/verisign/roots/VeriSign-Class%203-Public-Primary-Certification-Authority-G5.pem',
            filename='certs/rootCA.pem')

        # attach policy to certificate
        if not self.policydocument:
            self.pd = ('{\n'	
                  '     "Version": "2012-10-17",\n'	
                  '     "Statement": [{\n'	
                  '     "Effect":	"Allow",\n'
                  '       "Action":["iot:*"],\n'	
                  '       "Resource": ["*"]\n'
                  '     }]\n'
                  '}\n'
                 )  
            self.policydocument = "policydocument"
            text_file = open(self.policydocument, "w")
            text_file.write(self.pd)
            text_file.close()
        if not self.policyname:
            self.policyname = 'PubSubToAnyTopic'
        # policyname might already exist
        try:
                print("If the policy name already exists then creating it will fail. You can ignore this error.") 
                check_output('aws iot --endpoint {0} create-policy --policy-name {1} --policy-document file://{2} > arnresponse.txt'.format(self.AWSCERTURL,self.policyname,self.policydocument), shell=True)
        except CalledProcessError as e:
                check_output('aws iot --endpoint {0} get-policy --policy-name {1} > arnresponse.txt'.format(self.AWSCERTURL,self.policyname), shell=True)
        with open('arnresponse.txt') as data_file:    
                self.data = json.load(data_file)
        self.run(['aws','iot','-­‐endpoint­‐url',self.AWSCERTURL,'attach-­principal-­policy','-­‐principal-­arn',self.data["policyArn"],'--policy-name',self.policyname])	
        check_output('rm arnresponse.txt', shell=True)
        if self.thing:
                check_output('aws iot --endpoint {0} create-thing --thing-name {1}'.format(self.AWSCERTURL,self.thing), shell=True)
                print("Created Thing: %s" % self.thing)
        return True

    def run(self, cmd, **kwargs):
        return True

