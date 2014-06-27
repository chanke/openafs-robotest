
*** Settings ***
Documentation    Install the OpenAFS server and client binaries.
Library          lib/Install.py
Suite Setup      Installation Setup    ${DIST}

*** Test Cases ***
Install OpenAFS client
    OpenAFS client is not installed
    Install OpenAFS client
    OpenAFS client is installed

Install OpenAFS server
    OpenAFS server is not installed
    Install OpenAFS server
    OpenAFS server is installed

