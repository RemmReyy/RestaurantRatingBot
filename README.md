# Restaurant Rating System

## Overview
This system evaluates restaurant experiences based on three key parameters and determines overall customer satisfaction using fuzzy logic principles.

## Input Parameters
The system takes into account three input parameters:
1. **Food quality** (food_quality)
2. **Service quality** (service)
3. **Ambience** (ambience)

## Linguistic Terms
Each parameter has three linguistic terms:
- Poor
- Average
- Excellent

## Output Variable
The output variable "satisfaction" has 5 terms:
- Very low
- Low
- Medium
- High
- Very high

## System Operation
The system uses triangular membership functions and 11 rules that cover various combinations:
- Rules for very low satisfaction (when everything is poor)
- Rules for low satisfaction (when most parameters are poor)
- Rules for medium satisfaction (balanced situations)
- Rules for high satisfaction (when most parameters are good)
- Rules for very high satisfaction (when everything is excellent)
