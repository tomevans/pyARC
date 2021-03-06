import pdb, sys, os, time
import numpy as np
import scipy.interpolate
import tempfile


"""
This module contains routines for evaluating the log likelihood for some standard atmosphere models.
"""


def ClearChemEqIsothermTransmission( parsarr, keys, ARC ):
    """
    Evaluates the log likelihood for a clear atmosphere in chemical equilibrium
    assuming an isothermal PT profile given an observed spectrum for the planet. 
    Free parameters are a vertical offset (dRpRs), planetary temperature (Teff), 
    atmospheric metallicity (MdH), and the C/O ratio (COratio).

    Inputs:
    parsarr - Array containing values for each of the model parameters.
    keys - String labels for each parameter in parsarr that can be used to 
           map to the prior functions.
    ARC - An ARC object.
    """
    
    t1 = time.time()
    tmpdir = os.path.join( os.getcwd(), 'tmp' )
    if os.path.isdir( tmpdir )==False:
        os.makedirs( tmpdir )

    datasets = ARC.TransmissionData.keys()
    ndatasets = len( datasets )
    DataArr = []
    UncArr = []    
    for i in range( ndatasets ):
        dataseti = ARC.TransmissionData[datasets[i]]
        DataArr += [ dataseti[:,2] ]
        UncArr += [ dataseti[:,3] ]        
    DataArr = np.concatenate( DataArr )
    UncArr = np.concatenate( UncArr )

    npar = len( keys )
    pars = {}
    for i in range( npar ):
        pars[keys[i]] = parsarr[i]

    # Evaluate the prior likelihood:
    logp_prior = 0
    for key in pars.keys():
        logp_prior += ARC.Priors[key]( pars[key] )

    # If we're in an allowable region of parameter space,
    # proceed to run ATMO:
    if np.isfinite( logp_prior ):
        # Ensure atmosphere is isothermal:
        ARC.ATMO.fin = None
        # Install values for the free parameters:
        ARC.ATMO.teff = pars['Teff']
        ARC.ATMO.MdH = pars['MdH']
        ARC.ATMO.COratio = pars['COratio']
        if ARC.verbose==True:
            print '\nSetting:\nTeff = {0} K\nMdH = {1}\nCOratio = {2}'.\
                  format( ATC.ATMO.teff, ARC.ATMO.MdH, ARC.ATMO.COratio )
        # Use tempfile to create input and output files so that there
        # will be no duplication e.g. if running many walkers: 
        tempfileobj = tempfile.NamedTemporaryFile( mode='w+b', dir=tmpdir, suffix='.in', delete=False )
        ARC.ATMO.infile_path = tempfileobj.name
        ARC.ATMO.ftrans_spec = tempfileobj.name.replace( '.in', '.ncdf' )

        # Compute the model transmission spectrum:
        ARC.ATMO.RunATMO()
        ARC.ATMO.ReadTransmissionModel( ncdf_fpath=ARC.ATMO.ftrans_spec )
        WavMicronModel = ARC.ATMO.TransmissionModel[:,0]
        RpRsModel = ARC.ATMO.TransmissionModel[:,1] - pars['dRpRs']

        # Bin the transmission spectrum into the data bandpasses:
        interpf = scipy.interpolate.interp1d( WavMicronModel, RpRsModel )        
        datasets = ARC.TransmissionData.keys()
        ndatasets = len( datasets )
        ModelArr = []
        for i in range( ndatasets ):
            dataseti = ARC.TransmissionData[datasets[i]]
            ledges = dataseti[:,0]
            uedges = dataseti[:,1]
            nchannels = len( ledges )
            ModelArri = np.zeros( nchannels )
            for j in range( nchannels ):
                # Binning the model could be done more carefully with
                # actual instrument throughputs defined:
                WavChannel = np.r_[ ledges[j]:uedges[j]:1j*100 ]
                ModelArri[j] = np.mean( interpf( WavChannel ) )
            ModelArr += [ ModelArri ]
        ModelArr = np.concatenate( ModelArr )

        # Compute the residuals and data log likelihood:
        ResidsArr = DataArr - ModelArr
        ndat = len( ResidsArr )
        logp_data = logp_mvnormal_whitenoise( ResidsArr, UncArr, ndat )
        os.remove( ARC.ATMO.infile_path )
        os.remove( ARC.ATMO.ftrans_spec ) # in future, want to save these models at each step
        # TODO = COULD SAVE ALL OF THESE TRANSMISSION SPECTRA
        # FOR PLOTTING AT THE END
        logp = logp_prior + logp_data
    else:
        logp = -np.inf
    t2 = time.time()
    return logp


def ClearChemManIsothermTransmission( parsarr, keys, ARC ):
    """
    Evaluates the log likelihood for a clear atmosphere in with manual abundances
    for specified chemical species assuming an isothermal PT profile given an 
    observed spectrum for the planet. 
    Free parameters are a vertical offset (dRpRs), planetary temperature (Teff), 
    and the various chemical abundances (e.g. H2O, CO, CH4).

    Inputs:
    parsarr - Array containing values for each of the model parameters.
    keys - String labels for each parameter in parsarr that can be used to 
           map to the prior functions.
    ARC - An ARC object.
    """
    
    t1 = time.time()
    tmpdir = os.path.join( os.getcwd(), 'tmp' )
    if os.path.isdir( tmpdir )==False:
        os.makedirs( tmpdir )

    datasets = ARC.TransmissionData.keys()
    ndatasets = len( datasets )
    DataArr = []
    UncArr = []    
    for i in range( ndatasets ):
        dataseti = ARC.TransmissionData[datasets[i]]
        DataArr += [ dataseti[:,2] ]
        UncArr += [ dataseti[:,3] ]        
    DataArr = np.concatenate( DataArr )
    UncArr = np.concatenate( UncArr )

    npar = len( keys )
    pars = {}
    for i in range( npar ):
        pars[keys[i]] = parsarr[i]

    # Evaluate the prior likelihood:
    logp_prior = 0
    for key in pars.keys():
        logp_prior += ARC.Priors[key]( pars[key] )

    # If we're in an allowable region of parameter space,
    # proceed to run ATMO:
    if np.isfinite( logp_prior ):
        # Ensure atmosphere is isothermal:
        ARC.ATMO.fin = None
        # Install values for the free parameters:
        ARC.ATMO.teff = pars['Teff']
        # Install the free abundances manually:
        ARC.ATMO.chem = 'man'
        if ARC.verbose==True:
            print '\nSetting abundances:'
            for key in ARC.FreeSpecies:
                ARC.ATMO.abundances[key] = pars[key]
                print ' {0} --> {1}'.format( key, ARC.ATMO.abundances[key] )
            print 'Teff = {0} K\n'.format( ARC.ATMO.teff )
            
        # Use tempfile to create input and output files so that there
        # will be no duplication e.g. if running many walkers: 
        tempfileobj = tempfile.NamedTemporaryFile( mode='w+b', dir=tmpdir, suffix='.in', delete=False )
        ARC.ATMO.infile_path = tempfileobj.name
        ARC.ATMO.ftrans_spec = tempfileobj.name.replace( '.in', '.ncdf' )
        
        # Compute the model transmission spectrum:
        ARC.ATMO.RunATMO()
        
        ARC.ATMO.ReadTransmissionModel( ncdf_fpath=ARC.ATMO.ftrans_spec )
        WavMicronModel = ARC.ATMO.TransmissionModel[:,0]
        RpRsModel = ARC.ATMO.TransmissionModel[:,1] - pars['dRpRs']

        # Bin the transmission spectrum into the data bandpasses:
        interpf = scipy.interpolate.interp1d( WavMicronModel, RpRsModel )
        datasets = ARC.TransmissionData.keys()
        ndatasets = len( datasets )
        WavArr = []
        ModelArr = []
        for i in range( ndatasets ):
            dataseti = ARC.TransmissionData[datasets[i]]
            ledges = dataseti[:,0]
            uedges = dataseti[:,1]
            nchannels = len( ledges )
            WavArri = np.zeros( nchannels )
            ModelArri = np.zeros( nchannels )
            for j in range( nchannels ):
                # Binning the model could be done more carefully with
                # actual instrument throughputs defined:
                WavChannel = np.r_[ ledges[j]:uedges[j]:1j*100 ]
                WavArri[j] = 0.5*( ledges[j] + uedges[j] )
                ModelArri[j] = np.mean( interpf( WavChannel ) )
            WavArr += [ WavArri ]
            ModelArr += [ ModelArri ]
        WavArr = np.concatenate( WavArr )
        ModelArr = np.concatenate( ModelArr )

        # Compute the residuals and data log likelihood:
        ResidsArr = DataArr - ModelArr
        ndat = len( ResidsArr )
        logp_data = logp_mvnormal_whitenoise( ResidsArr, UncArr, ndat )
        os.remove( ARC.ATMO.infile_path )
        os.remove( ARC.ATMO.ftrans_spec ) # in future, want to save these models at each step
        # TODO = COULD SAVE ALL OF THESE TRANSMISSION SPECTRA
        # FOR PLOTTING AT THE END
        logp = logp_prior + logp_data
    else:
        logp = -np.inf
    t2 = time.time()
    return logp


def logp_mvnormal_whitenoise( r, u, n  ):
    """
    Log likelihood of a multivariate normal distribution
    with diagonal covariance matrix.
    """
    term1 = -np.sum( np.log( u ) )
    term2 = -0.5*np.sum( ( r/u )**2. )
    return term1 + term2 - 0.5*n*np.log( 2*np.pi )

    
