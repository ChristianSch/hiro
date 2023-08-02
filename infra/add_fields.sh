#!/bin/bash
curl -X POST -H 'Content-type:application/json' --data-binary '{
    "add-field":{
        "name":"body",
        "type":"string",
        "stored":true }
    }' http://localhost:8983/api/cores/hproto/schema

curl -X POST -H 'Content-type:application/json' --data-binary '{
    "add-field":{
        "name":"title",
        "type":"string",
        "stored":true }
    }' http://localhost:8983/api/cores/hproto/schema