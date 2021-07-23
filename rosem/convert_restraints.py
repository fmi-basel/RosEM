import re
import sys
import math



class PhenixToRosetta:
    def __init__(self, geo_file):
        self.geo_file = geo_file
        self.convert()

    def convert(self):
        with open(self.geo_file, 'r') as f:
            scan = False
            start_of_block = False
            residue_block = []
            dihedrals = []
            counter1, counter2 = 0, 0
            for line in f:
                if re.search("Reference torsion angle restraints", line):
                    scan = True
                    continue
                if scan:
                    if re.match("dihedral.*", line):
                        start_of_block = True
                    if start_of_block:
                        if re.match(".*pdb=\".*\"", line):
                            counter1 += 1
                            print(line)
                            if re.match('.*pdb=\"\s*\w+\'*\s+\w+\s+\w{1}\s*-*\d+\s+\"', line):
                                
                                residue = re.match(".*pdb=\"\s*(\w+\'*)\s+\w+\s+(\w{1})\s*(-*\d+)\s+\"", line)
                                # Group 1 = Atom name Group 2 = Chain Group 3 = Residue Number
                                residue_block.append((residue.group(1).replace(" ",""), residue.group(2), residue.group(3)))
                                if residue.group(1).replace(" ", "") == "OXT":
                                    continue
                            else:
                                print("error")
                                raise SystemExit
                        if re.match(".*([0-9\.e+-]+\s+){7}.*", line):
                            #print("yes2")
                            counter2 += 1
                            params = re.match("\s+([0-9\.e+-]+)\s+.*", line)
                            angle = params.group(1)
                            dihedrals.append((residue_block, angle))
                            residue_block = []
                            start_of_block = False
                            #print(dihedrals)
                    else:
                        continue
            print(counter1 / 4)
            print(counter2)

        with open("reference_model_restraints.cst","w+") as f:
            for dihedral in dihedrals:
                angle = math.radians(float(dihedral[1]))
                residues = dihedral[0]
                dihedrals_rosetta = []
                dihedrals_rosetta = ['Dihedral ']
                for residue in residues:
                    print(residue)
                    dihedrals_rosetta.append('{} {}{} '.format(residue[0], residue[2], residue[1]))
                dihedrals_rosetta.append('CIRCULARHARMONIC {} 0.35\n'.format(angle))
                dihedrals_rosetta = ''.join(dihedrals_rosetta)
                f.writelines(dihedrals_rosetta)

if __name__ == '__main__':
    geo_file = sys.argv[1]
    PhenixToRosetta(geo_file)
