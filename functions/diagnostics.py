#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Time-stamp: <2018-09-17 11:55:41 lukbrunn>

(c) 2018 under a MIT License (https://mit-license.org)

Authors:
- Ruth Lorenz || ruth.lorenz@env.ethz.ch
- Lukas Brunner || lukas.brunner@env.ethz.ch

Abstract:

"""
import os
import logging
import numpy as np
import netCDF4 as nc
from tempfile import TemporaryDirectory
from cdo import Cdo
cdo = Cdo()

logger = logging.getLogger(__name__)
REGION_DIR = '{}/../cdo_data/'.format(os.path.dirname(__file__))


def calc_Rnet(infile, outname, variable, derived = True,
              workdir = None):
    """
    Procedure to calculate derived diagnostic net radiation.

    Parameters:
    - infile (string): Input filename incl. full path
    - outname (string): Output filename incl. full path but without extension
    - variable (string): one of the variables used in calculation present in infile
    optional:
    - derived (boolean): standard CMIP variable or derived from other variables?
    - workdir (string): temporary directory where intermediate files are
                        stored, default is in same location as script run
    Returns:
    - The name of the produced file (string)
    """
    if not derived:
        logger.error('This function is for derived variables, ' +
                     'something is wrong here.')
        sys.exit
    if not workdir:
        workdir = 'tmp_work'
    if (os.access(workdir, os.F_OK) == False):
        os.makedirs(workdir)

    variable1 = 'rlds'
    variable2 = 'rlus'
    variable3 = 'rsds'
    variable4 = 'rsus'

    # find files for other variables
    infile1 = infile.replace(variable, variable1)
    infile2 = infile.replace(variable, variable2)
    infile3 = infile.replace(variable, variable3)
    infile4 = infile.replace(variable, variable4)

    outname_rnet = outname.replace(variable, 'rnet')
    outfile = '%s.nc' %(outname_rnet)

    lwnet = cdo.sub(input = '%s %s' %(infile, infile2))
    swnet = cdo.sub(input = '%s %s' %(infile3, infile4))
    rnetfile = cdo.add(input = '%s %s' %(lwnet, swnet))
    cdo.chname('%s,rnet' %(variable), input = rnetfile,
               output = outfile)
    return outfile

def calc_diag(infile,
              outname,
              diagnostic,
              masko,
              syear,
              eyear,
              season,
              region,
              kind=None,
              overwrite=False,
              variable=None,  # TODO: needed?
              derived=False,  # TODO: needed?
):
    """
    TODO: rewrite docstring!

    Procedure that calculates diagnostics for weighting method

    Parameters:
    - infile (string): Input filename incl. full path
    - outname (string): Output filename incl. full path but without extension
    - diagnostic (string): the diagnostic to be calculated, can be the same as
                           the variable name but some require extra steps
    optional:
    - variable (string): the variable to be processed, for derived diagnostics
                         one of them to find the files
    - derived (boolean): standard CMIP variable or derived from other variables?
    - workdir (string): temporary directory where intermediate files are
                        stored, default is in same location as script run
    - masko (boolean): mask ocean or not?
    - landseamask (string): if masko = True we need the path to a land sea mask
    - syear (int): the start year if the original file is cut
    - eyear (int): the end year if the original file is cut
    - seasons (list of strings): a season JJA, MAM, DJF, SON or ANN for annual,
                                 if not given all of them calculated
    - kind (list of strings): what kind of diagnostic to be calculated,
                              can be CLIM, STD, TREND, CORR, if not given CLIM,
                              STD and TREND are calculated
    - region (string): a region name if the region should be cut
    - areadir (string): a path to the directory where the lat lon of the
                        regions are stored
    Returns:
    str (filename of saved file)
    """
    filename_global = '{}_{}-{}_{}_GLOBAL.nc'.format(outname, syear, eyear, season)  # TODO: needed?
    filename_global_kind = '{}_{}-{}_{}_{}_GLOBAL.nc'.format(outname, syear, eyear, season, kind)
    filename_region = '{}_{}-{}_{}_{}.nc'.format(outname, syear, eyear, season, region)
    filename_region_kind = '{}_{}-{}_{}_{}_{}.nc'.format(outname, syear, eyear, season, kind, region)

    if not overwrite and (os.path.isfile(filename_global) and
                          os.path.isfile(filename_global_kind) and
                          os.path.isfile(filename_region) and
                          os.path.isfile(filename_region_kind)):
        logger.debug('Diagnostic already exists & overwrite=False, skipping.')
        if region == 'GLOBAL':
            if kind is None:
                return filename_global
            return filename_global_kind
        else:
            if kind is None:
                return filename_region
            return filename_region_kind

    # NOTE: I'm still not sure about the difference between diagnostic and variable
    if variable is None:
        variable = diagnostic

    if derived:
        if diagnostic == 'rnet':
            derived_file = calc_Rnet(infile, outname, variable, derived=True)
            outname = outname.replace(variable, 'rnet')
            variable = 'rnet'
            logger.debug(outname)
        else:
            raise NotImplementedError('Only Rnet implemented so far')
        infile = derived_file

    # read infile and get units of variable
    fh = nc.Dataset(infile, mode = 'r')
    unit = fh.variables[variable].units
    fh.close()

    with TemporaryDirectory(dir='/net/h2o/climphys/tmp') as tmpdir:
        # ----------------------
        # NOTE: cdo operations require different input/output files.
        # - the first operation takes the original input an creates 'tmpfile'
        # - all subsequent operations (except the last) take either 'tmpfile'
        #   and create 'tmpfile2' or vice versa
        # - the last operation takes 'tmpfile(2)' and creates the output file
        # ----------------------
        tmpfile = os.path.join(tmpdir, 'temp.nc')
        tmpfile2 = os.path.join(tmpdir, 'temp2.nc')

        # map longitude
        cdo.sellonlatbox(-180, 180, -90, 90, input=infile, output=tmpfile)

        # first change some units if necessary
        # TODO: is this really something that should be done here?
        # TODO: what is the effect of this?
        if variable == 'pr' and  unit == 'kg m-2 s-1':
            newunit = "mm/day"
            cdo.mulc(24*60*60, input=tmpfile, output=tmpfile2)
            cdo.chunit('"kg m-2 s-1",%s' %(newunit),
                       input=tmpfile2,
                       output=tmpfile)
        elif variable == 'huss':
            newunit = "g/kg"
            cdo.mulc(1000, options='-b 64', input=tmpfile, output=tmpfile2)
            if unit == 'kg/kg':
                cdo.chunit('"kg/kg",%s' %(newunit), input=tmpfile2, output=tmpfile)
            if unit == 'kg kg-1':
                cdo.chunit('"kg kg-1",%s' %(newunit), input=tmpfile2, output=tmpfile)
            if unit == '1':
                cdo.chunit('"1",%s' %(newunit), input=tmpfile2, output=tmpfile)
            else:
                logger.warning('Unit {} for variable {} not covered!'.format(unit, variable))
        elif unit == 'K' and (variable == 'tas' or
                              variable == 'tasmax' or
                              variable == 'tasmin' or
                              variable == 'tos'):
            newunit = "degC"
            cdo.subc(273.15, input=tmpfile, output=tmpfile2)
            cdo.chunit('"K",%s' %(newunit), input=tmpfile2, output=tmpfile)

        if masko:
            filename_mask = os.path.join(REGION_DIR, 'seamask_g025.nc')
            cdo.setmissval(0,
                           input="-mul -eqc,1 %s %s" %(filename_mask, tmpfile),
                           output=tmpfile2)
            cdo.setmissval(1e20, input=tmpfile2, output=tmpfile)

        if variable == 'tos':
            cdo.setvrange('0,40', input=tmpfile, output=tmpfile2)
            os.rename(tmpfile2, tmpfile)

        if season == 'ANN':
            cdo.seldate('%s-01-01,%s-12-31' %(syear, eyear),
                        input=tmpfile, output=filename_global)
        else:
            cdo.seldate('%s-01-01,%s-12-31' %(syear, eyear),
                        input=tmpfile, output=tmpfile2)
            cdo.selseas(season, input=tmpfile2, output=filename_global)

        # NOTE, DELETE: data saved, clean tmpfiles
        os.remove(tmpfile)  # remove to not make stupid mistakes
        os.remove(tmpfile2)  # remove to not make stupid mistakes

        # NOTE: is this an inconsistency?
        # - Climatology is aggregated as time mean of annual mean (in the case of 'ANN')
        # - Standard deviation is aggregated directly from the data
        # -> STD is NOT the standard deviation from CLIM!
        if kind == 'CLIM' and season == 'ANN':
            cdo.yearmean(input=filename_global, output=tmpfile)
            cdo.timmean(input=tmpfile2, output=filename_global_kind)  # save output
        elif kind == 'CLIM':
            cdo.seasmean(input=filename_global, output=tmpfile)
            cdo.yseasmean(input=tmpfile, output=filename_global_kind)  # save output
        elif kind == 'STD':
            cdo.detrend(input=filename_global, output=tmpfile)
            cdo.timstd(input=tmpfile, output=filename_global_kind) # save output
        elif kind == 'TREND':
            cdo.regres(input=filename_global, output=filename_global_kind) # save output

        if region != 'GLOBAL':
            mask = np.loadtxt('%s/%s.txt' %(REGION_DIR, region))
            lonmax = np.max(mask[:, 0])
            lonmin = np.min(mask[:, 0])
            latmax = np.max(mask[:, 1])
            latmin = np.min(mask[:, 1])

            cdo.sellonlatbox(lonmin,lonmax,latmin,latmax,
                             input=filename_global,
                             output=filename_region)
            cdo.sellonlatbox(lonmin,lonmax,latmin,latmax,
                             input=filename_global_kind,
                             output=filename_region_kind)

    if region == 'GLOBAL':
        if kind is None:
            return filename_global
        return filename_global_kind
    else:
        if kind is None:
            return filename_region
        return filename_region_kind


def calc_CORR(infile,
              base_path,
              variable1,
              variable2,
              masko,
              syear,
              eyear,
              season,
              region,
              overwrite=False):
    """
    Procedure to calculate derived diagnostic correlation between
    two variables (e.g. temperature tas and cloud cover clt).

    Parameters:
    - infile (string): Input filename incl. full path
    - outname (string): Output filename incl. full path but without extension
    - variable1 (string): first variable in correlation
    - variable2 (string): second variable in correlation
    optional:
    - derived (boolean): standard CMIP variable or derived from other variables?
    - workdir (string): temporary directory where intermediate files are
                        stored, default is in same location as script run
    - masko (boolean): mask ocean or not?
    - landseamask (string): if masko = True we need the path to a land sea mask
    - syear (int): the start year if the original file is cut
    - eyear (int): the end year if the original file is cut
    - seasons (list of strings): a season JJA, MAM, DJF, SON or ANN for annual,
                                 if not given all of them calculated
    - region (string): a region name if the region should be cut
    - areadir (string): a path to the directory where the lat lon of the
                        regions are stored
    Returns:
    - Nothing, the produced file is outfile
    """

    # create template for output files
    outname = os.path.join(
        base_path,
        os.path.basename(infile).replace('clt', 'tasclt'))  # TODO, DEBUG !!! remove hardcoded stuff!
    outname = outname.replace('.nc', '')

    filename_global_kind = '{}_{}-{}_{}_CORR_GLOBAL.nc'.format(outname, syear, eyear, season)
    filename_region_kind = '{}_{}-{}_{}_CORR_{}.nc'.format(outname, syear, eyear, season, region)
    if not overwrite and (os.path.isfile(filename_global_kind) and
                          os.path.isfile(filename_region_kind)):
        if region == 'GLOBAL':
            return filename_global_kind
        return filename_region_kind

    base_path1 = base_path.replace('tasclt', variable1)
    os.makedirs(base_path1, exist_ok=True)
    outname = os.path.join(base_path1, os.path.basename(infile)).replace('.nc', '')

    filename_diag1 = calc_diag(infile, outname,
                               diagnostic=variable1,
                               masko=masko,
                               syear=syear,
                               eyear=eyear,
                               season=season,
                               region='GLOBAL',
                               overwrite=overwrite,
                               kind=None)

    base_path2 = base_path.replace('tasclt', variable2)
    os.makedirs(base_path2, exist_ok=True)
    infile2 = infile.replace(variable1, variable2)
    outname = os.path.join(base_path2, os.path.basename(infile2)).replace('.nc', '')
    filename_diag2 = calc_diag(infile2, outname,
                               diagnostic=variable2,
                               masko=masko,
                               syear=syear,
                               eyear=eyear,
                               season=season,
                               region='GLOBAL',
                               overwrite=overwrite,
                               kind=None)

    with TemporaryDirectory(dir='/net/h2o/climphys/tmp') as tmpdir:
        tmpfile = os.path.join(tmpdir, 'temp.nc')
        tmpfile2 = os.path.join(tmpdir, 'temp2.nc')

        cdo.timcor(input='{} {}'.format(filename_diag1, filename_diag2),
                   output=tmpfile)
        cdo.chname('%s,%s%s' %(variable1, variable2, variable1),
                   input=tmpfile, output=tmpfile2)
        cdo.setattribute('%s%s@units=-' %(variable2, variable1),
                         input=tmpfile2, output=tmpfile)
        cdo.setvrange('-1,1', input=tmpfile, output=filename_global_kind)

    if region != 'GLOBAL':
        mask = np.loadtxt('%s/%s.txt' %(REGION_DIR, region))
        lonmax = np.max(mask[:, 0])
        lonmin = np.min(mask[:, 0])
        latmax = np.max(mask[:, 1])
        latmin = np.min(mask[:, 1])

        cdo.sellonlatbox(lonmin,lonmax,latmin,latmax,
                         input=filename_global_kind,
                         output=filename_region_kind)

    if region == 'GLOBAL':
        return filename_global_kind
    return filename_region_kind