# Copyright (c) 2014 Sine Nomine Associates
# See LICENSE

*** Settings ***
Documentation     Common keywords and variables for the OpenAFS test suite.
Library           OperatingSystem
Library           String
Library           OpenAFSLibrary

*** Keywords ***
TODO
    [Arguments]  ${msg}=Not implemented
    Fail  TODO: ${msg}

