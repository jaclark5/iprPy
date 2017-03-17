import os
import atomman.lammps as lmp

def test_lammps_stress_version(lammps_command):
    """Does a quick call to a LAMMPS executable to test the compute stress version"""
    if True:
    #try:
        lmp.run(lammps_command, 
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                             'compute_stress_test1.in'), 
                logfile='compute_stress_test.lammps')
        version = 'NULL'
    else:#except:
        try:
            lmp.run(lammps_command, 
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compute_stress_test2.in'),
                    logfile='compute_stress_test.lammps')
            version = ''
        except:
            raise ValueError('LAMMPS command failed both known versions for compute stress')
    
    os.remove('compute_stress_test.lammps')
    return version
    