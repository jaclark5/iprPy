# coding: utf-8

# Python script created by Lucas Hale and Norman Luu.

# Standard library imports
from pathlib import Path
import shutil
import datetime

# http://www.numpy.org/
import numpy as np 

# https://github.com/usnistgov/atomman 
import atomman as am
import atomman.lammps as lmp
import atomman.unitconvert as uc

# iprPy imports
from ...tools import filltemplate, read_calc_file

# Define calculation metadata
parent_module = '.'.join(__name__.split('.')[:-1])

def stackingfaultrelax(lammps_command, system, potential,
                       mpi_command=None, sim_directory=None,
                       cutboxvector='c',
                       etol=0.0, ftol=0.0,
                       maxiter=10000, maxeval=100000,
                       dmax=uc.set_in_units(0.01, 'angstrom'),
                       lammps_date=None):
    """
    Perform a stacking fault relaxation simulation for a single faultshift.
    
    Parameters
    ----------
    lammps_command :str
        Command for running LAMMPS.
    system : atomman.System
        The system containing a stacking fault.
    potential : atomman.lammps.Potential
        The LAMMPS implemented potential to use.
    mpi_command : str, optional
        The MPI command for running LAMMPS in parallel.  If not given, LAMMPS
        will run serially.
    sim_directory : str, optional
        The path to the directory to perform the simulation in.  If not
        given, will use the current working directory.
    cutboxvector : str, optional
        Indicates which of the three system box vectors, 'a', 'b', or 'c', has
        the non-periodic boundary (default is 'c').  Fault plane normal is
        defined by the cross of the other two box vectors.
    etol : float, optional
        The energy tolerance for the structure minimization. This value is
        unitless. (Default is 0.0).
    ftol : float, optional
        The force tolerance for the structure minimization. This value is in
        units of force. (Default is 0.0).
    maxiter : int, optional
        The maximum number of minimization iterations to use (default is 
        10000).
    maxeval : int, optional
        The maximum number of minimization evaluations to use (default is 
        100000).
    dmax : float, optional
        The maximum distance in length units that any atom is allowed to relax
        in any direction during a single minimization iteration (default is
        0.01 Angstroms).
    lammps_date : datetime.date or None, optional
        The date version of the LAMMPS executable.  If None, will be identified
        from the lammps_command (default is None).
    
    Returns
    -------
    dict
        Dictionary of results consisting of keys:
        
        - **'logfile'** (*str*) - The filename of the LAMMPS log file.
        - **'dumpfile'** (*str*) - The filename of the LAMMPS dump file
          of the relaxed system.
        - **'system'** (*atomman.System*) - The relaxed system.
        - **'E_total'** (*float*) - The total potential energy of the relaxed
          system.
    
    Raises
    ------
    ValueError
        For invalid cutboxvectors.
    """
    
    # Give correct LAMMPS fix setforce command
    if cutboxvector == 'a':
        fix_cut_setforce = 'fix cut all setforce NULL 0 0'    
    elif cutboxvector == 'b':
        fix_cut_setforce = 'fix cut all setforce 0 NULL 0'
    elif cutboxvector == 'c':
        fix_cut_setforce = 'fix cut all setforce 0 0 NULL'    
    else: 
        raise ValueError('Invalid cutboxvector')
    
    if sim_directory is not None:
        # Create sim_directory if it doesn't exist
        sim_directory = Path(sim_directory)
        if not sim_directory.is_dir():
            sim_directory.mkdir()
        sim_directory = sim_directory.as_posix()+'/'
    else:
        # Set sim_directory if is None
        sim_directory = ''
    
    # Get lammps units
    lammps_units = lmp.style.unit(potential.units)
    
    #Get lammps version date
    if lammps_date is None:
        lammps_date = lmp.checkversion(lammps_command)['date']
    
    # Define lammps variables
    lammps_variables = {}
    system_info = system.dump('atom_data',
                              f=Path(sim_directory, 'system.dat').as_posix(),
                              potential=potential)
    lammps_variables['atomman_system_pair_info'] = system_info
    lammps_variables['fix_cut_setforce'] = fix_cut_setforce
    lammps_variables['sim_directory'] = sim_directory
    lammps_variables['etol'] = etol
    lammps_variables['ftol'] = uc.get_in_units(ftol, lammps_units['force'])
    lammps_variables['maxiter'] = maxiter
    lammps_variables['maxeval'] = maxeval
    lammps_variables['dmax'] = uc.get_in_units(dmax, lammps_units['length'])
    
    # Set dump_modify format based on dump_modify_version
    if lammps_date < datetime.date(2016, 8, 3):
        lammps_variables['dump_modify_format'] = '"%i %i %.13e %.13e %.13e %.13e"'
    else:
        lammps_variables['dump_modify_format'] = 'float %.13e'
    
    # Write lammps input script
    template_file = 'sfmin.template'
    lammps_script = Path(sim_directory, 'sfmin.in')
    template = read_calc_file(parent_module, template_file)
    with open(lammps_script, 'w') as f:
        f.write(filltemplate(template, lammps_variables, '<', '>'))
    
    # Run LAMMPS
    output = lmp.run(lammps_command, lammps_script.as_posix(), mpi_command,
                     logfile=Path(sim_directory, 'log.lammps').as_posix())
    
    # Extract output values
    thermo = output.simulations[-1]['thermo']
    logfile = Path(sim_directory, 'log.lammps').as_posix()
    dumpfile = Path(sim_directory, '%i.dump' % thermo.Step.values[-1]).as_posix()
    E_total = uc.set_in_units(thermo.PotEng.values[-1],
                              lammps_units['energy'])
    
    # Load relaxed system
    system = am.load('atom_dump', dumpfile, symbols=system.symbols)
    
    # Return results
    results_dict = {}
    results_dict['logfile'] = logfile
    results_dict['dumpfile'] = dumpfile
    results_dict['system'] = system
    results_dict['E_total'] = E_total
    
    return results_dict

def stackingfaultmap(lammps_command, ucell, potential, hkl,
                     mpi_command=None, sizemults=None, minwidth=None, even=False,
                     a1vect_uvw=None, a2vect_uvw=None, conventional_setting='p',
                     cutboxvector='c', faultpos_rel=None, faultpos_cart=None,
                     num_a1=10, num_a2=10, atomshift=None, shiftindex=None,
                     etol=0.0, ftol=0.0, maxiter=10000, maxeval=100000,
                     dmax=uc.set_in_units(0.01, 'angstrom')): 
    """
    Computes a generalized stacking fault map for shifts along a regular 2D
    grid.
    
    Parameters
    ----------
    lammps_command :str
        Command for running LAMMPS.
    ucell : atomman.System
        The crystal unit cell to use as the basis of the stacking fault
        configurations.
    potential : atomman.lammps.Potential
        The LAMMPS implemented potential to use.
    hkl : array-like object
        The Miller(-Bravais) crystal fault plane relative to ucell.
    mpi_command : str, optional
        The MPI command for running LAMMPS in parallel.  If not given, LAMMPS
        will run serially.
    sizemults : list or tuple, optional
        The three System.supersize multipliers [a_mult, b_mult, c_mult] to use on the
        rotated cell to build the final system. Note that the cutboxvector sizemult
        must be an integer and not a tuple.  Default value is [1, 1, 1].
    minwidth : float, optional
        If given, the sizemult along the cutboxvector will be selected such that the
        width of the resulting final system in that direction will be at least this
        value. If both sizemults and minwidth are given, then the larger of the two
        in the cutboxvector direction will be used. 
    even : bool, optional
        A True value means that the sizemult for cutboxvector will be made an even
        number by adding 1 if it is odd.  Default value is False.
    a1vect_uvw : array-like object, optional
        The crystal vector to use for one of the two shifting vectors.  If
        not given, will be set to the shortest in-plane lattice vector.
    a2vect_uvw : array-like object, optional
        The crystal vector to use for one of the two shifting vectors.  If
        not given, will be set to the shortest in-plane lattice vector not
        parallel to a1vect_uvw.
    conventional_setting : str, optional
        Allows for rotations of a primitive unit cell to be determined from
        (hkl) indices specified relative to a conventional unit cell.  Allowed
        settings: 'p' for primitive (no conversion), 'f' for face-centered,
        'i' for body-centered, and 'a', 'b', or 'c' for side-centered.  Default
        behavior is to perform no conversion, i.e. take (hkl) relative to the
        given ucell.
    cutboxvector : str, optional
        Indicates which of the three system box vectors, 'a', 'b', or 'c', to
        cut with a non-periodic boundary (default is 'c').
    faultpos_rel : float, optional
        The position to place the slip plane within the system given as a
        relative coordinate along the out-of-plane direction.  faultpos_rel
        and faultpos_cart cannot both be given.  Default value is 0.5 if 
        faultpos_cart is also not given.
    faultpos_cart : float, optional
        The position to place the slip plane within the system given as a
        Cartesian coordinate along the out-of-plane direction.  faultpos_rel
        and faultpos_cart cannot both be given.
    num_a1 : int, optional
        The number of fractional coordinates to evaluate along a1vect_uvw.
        Default value is 10.
    num_a2 : int, optional
        The number of fractional coordinates to evaluate along a2vect_uvw.
        Default value is 10.
    atomshift : array-like object, optional
        A Cartesian vector shift to apply to all atoms.  Can be used to shift
        atoms perpendicular to the fault plane to allow different termination
        planes to be cut.  Cannot be given with shiftindex.
    shiftindex : int, optional
        Allows for selection of different termination planes based on the
        preferred shift values determined by the underlying fault generation.
        Cannot be given with atomshift. If neither atomshift nor shiftindex
        given, then shiftindex will be set to 0.
    etol : float, optional
        The energy tolerance for the structure minimization. This value is
        unitless. (Default is 0.0).
    ftol : float, optional
        The force tolerance for the structure minimization. This value is in
        units of force. (Default is 0.0).
    maxiter : int, optional
        The maximum number of minimization iterations to use (default is 
        10000).
    maxeval : int, optional
        The maximum number of minimization evaluations to use (default is 
        100000).
    dmax : float, optional
        The maximum distance in length units that any atom is allowed to relax
        in any direction during a single minimization iteration (default is
        0.01 Angstroms).
    
    Returns
    -------
    dict
        Dictionary of results consisting of keys:
        
        - **'A_fault'** (*float*) - The area of the fault surface.
        - **'gamma'** (*atomman.defect.GammaSurface*) - A gamma surface
          plotting object.
    """
    # Construct stacking fault configuration generator
    gsf_gen = am.defect.StackingFault(hkl, ucell, cutboxvector=cutboxvector,
                                      a1vect_uvw=a1vect_uvw, a2vect_uvw=a2vect_uvw,
                                      conventional_setting=conventional_setting)
    
    # Check shift parameters
    if shiftindex is not None:
        assert atomshift is None, 'shiftindex and atomshift cannot both be given'
        atomshift = gsf_gen.shifts[shiftindex]
    elif atomshift is None:
        atomshift = gsf_gen.shifts[0]
    
    # Generate the free surface (zero-shift) configuration
    gsf_gen.surface(shift=atomshift, minwidth=minwidth, sizemults=sizemults,
                    even=even, faultpos_rel=faultpos_rel)
    
    abovefault = gsf_gen.abovefault
    cutindex = gsf_gen.cutindex
    A_fault = gsf_gen.surfacearea

    # Identify lammps_date version
    lammps_date = lmp.checkversion(lammps_command)['date']
    
    # Define lists
    a1vals = []
    a2vals = []
    E_totals = []
    disps = []

    # Loop over all shift combinations
    for a1, a2, sfsystem in gsf_gen.iterfaultmap(num_a1=num_a1, num_a2=num_a2):
        a1vals.append(a1)
        a2vals.append(a2)

        # Evaluate the system at the shift
        sim_directory = Path('a%.10f-b%.10f' % (a1, a2))
        relax = stackingfaultrelax(lammps_command, sfsystem, potential,
                                   mpi_command=mpi_command, 
                                   sim_directory=sim_directory,
                                   cutboxvector=cutboxvector,
                                   etol=etol, ftol=ftol, maxiter=maxiter,
                                   maxeval=maxeval, dmax=dmax,
                                   lammps_date=lammps_date)
        
        # Extract terms
        E_totals.append(relax['E_total'])
        pos = relax['system'].atoms.pos
        disps.append(pos[abovefault, cutindex].mean()
                   - pos[~abovefault, cutindex].mean())
    
    E_totals = np.array(E_totals)
    disps = np.array(disps)
    
    # Get zeroshift values
    E_total_0 = E_totals[0]
    disp_0 = disps[0]
    
    # Compute the stacking fault energies
    E_gsfs = (E_totals - E_total_0) / A_fault
    
    # Compute the change in displacement normal to fault plane
    delta_disps = disps - disp_0
    
    results_dict = {}
    results_dict['A_fault'] = A_fault
    results_dict['gamma'] = am.defect.GammaSurface(a1vect = gsf_gen.a1vect_uvw,
                                                   a2vect = gsf_gen.a2vect_uvw,
                                                   box = gsf_gen.ucell.box,
                                                   a1 = a1vals,
                                                   a2 = a2vals,
                                                   E_gsf = E_gsfs,
                                                   delta = delta_disps)

    return results_dict