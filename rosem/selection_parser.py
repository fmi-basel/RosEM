import re
from pyparsing import ParseException, Word, printables, infixNotation, Group, alphas, nums, White, opAssoc

class ResidueSelection:
    '''Compatible syntax:
    Residue name: resn
    Residue Index: resi
    Chain ID: chain
    -: from . to .
    and: and
    or: or
    '''
    def __init__(self, selection_string):
        self.selection_string = selection_string
        print("Selection string")
        print(self.selection_string)
        self.ops = ['and', 'or']
        self.selector_lst = []
        self.converted_lst = []
        self.remove_quotes()
        self.add_parantheses()
        self.selection_lst = self.parse_nested_expr()
        self.replace_name(self.selection_lst)
        self.replace_op(self.selection_lst)
        self.index_dict = {}

    def remove_quotes(self):
        if re.search('"', self.selection_string):
            print("removing quotes")
            self.selection_string = self.selection_string.replace('"', '')


    def add_parantheses(self):
        if not self.selection_string.startswith("("):
            self.selection_string = "({}".format(self.selection_string)
        if not self.selection_string.endswith(")"):
            self.selection_string = "{})".format(self.selection_string)

    def parse_nested_expr(self):
        varname = Word(alphas)
        integer = Word(nums + "-")#.setParseAction(lambda t: int(t[0]))

        comparisonOp = White(" ")
        term = varname | integer
        comparisonExpr = Group(term + comparisonOp + term)

        logicalExpr = infixNotation(comparisonExpr,
                                    [
                                        ('and', 2, opAssoc.LEFT),
                                        ('or', 2, opAssoc.LEFT),
                                    ])
        try:
            result = logicalExpr.parseString(self.selection_string).asList()
        except ParseException:
            print("exception parsing selection string")
            comparisonExpr = Group(term + comparisonOp + term + comparisonOp + term)

            logicalExpr = infixNotation(comparisonExpr,
                                        [
                                            ('and', 2, opAssoc.LEFT),
                                            ('or', 2, opAssoc.LEFT),
                                        ])
            result = logicalExpr.parseString(self.selection_string).asList()
        print("nested_expr")
        print(result)
        print(self.selection_string)
        return result



    def parse_hierachy(self, lst, indices=[], prev_i=-1):
        for i, item in enumerate(lst):
            if i == 0:
                indices.append(i)
            print("Item: {}, Index: {}".format(item, i))
            if isinstance(item, list):
                indices[-1] = i
                print("new indices list: {}".format(indices))
                hierachy(item, indices)
            else:
                indices[-1] = i
                if item in self.ops:
                    print("True")

                    new_indices = [x for x in indices]
                    print("new indices ops: {}".format(new_indices))
                    l_i = [x for x in indices]
                    l_i[-1] = i - 1
                    l_i = ''.join([str(x) for x in l_i])
                    r_i = [x for x in indices]
                    r_i[-1] = i + 1
                    r_i = ''.join([str(x) for x in r_i])
                    self.index_dict[''.join([str(x) for x in indices])] = [l_i, r_i]
                else:
                    print("indices list: {}".format(indices))
            if i + 1 == len(lst):
                indices.pop()
            prev_i = i

    def replace_name(self, lst, indices=[], prev_i=-1):
        for i, item in enumerate(lst):
            if i == 0:
                indices.append(i)
            print("Item: {}, Index: {}".format(item, i))
            if isinstance(item, list):
                indices[-1] = i
                print("new indices list: {}".format(indices))
                self.replace_name(item, indices)
            else:
                if not item in self.ops and not item is None:
                    if i == 0:
                        print(lst)
                        merged = ''.join([str(x) for x in lst])
                        print("merged")
                        print(merged)
                        selector_index = ''.join([str(x) for x in indices])
                        selector = self.name_parser(merged, selector_index)
                        lst[:] = [selector]
                        self.selector_lst.append(selector)
                    else:
                        print("delete {}".format(i))
                        #del lst[i]
            if i + 1 == len(lst):
                indices.pop()
            prev_i = i

    def replace_op(self, lst, indices=[]):
        for i, item in enumerate(lst):
            if i == 0:
                indices.append(i)
            print("Item: {}, Index: {}".format(item, i))
            if isinstance(item, list):
                indices[-1] = i
                print("new indices list: {}".format(indices))
                self.replace_op(item, indices)
            else:
                selector_index = ''.join([str(x) for x in indices]) + '0'
                indices[-1] = i
                if not item is None:
                    if item.lower() in self.ops:
                        l_i = [x for x in indices]
                        l_i[-1] = i - 1
                        l_i = ''.join([str(x) for x in l_i]) + '0'
                        r_i = [x for x in indices]
                        r_i[-1] = i + 1
                        r_i = ''.join([str(x) for x in r_i]) + '0'
                        if item.lower() == 'and':
                            self.converted_lst.append(
                                ("And", selector_index[:-1], "{},{}".format(l_i, r_i), False)
                                #"<And selector=\"{},{}\">".format(l_i, r_i)
                            )
                        elif item.lower() == 'or':
                            self.converted_lst.append(
                                ("Or", selector_index[:-1], "{},{}".format(l_i, r_i), False)
                                #"<Or selector=\"{},{}\">".format(l_i, r_i)
                            )
                        else:
                            print("delete {}".format(i))
                            #del lst[i]
            if i + 1 == len(lst):
                indices.pop()
            prev_i = i


    def name_parser(self, name, selector_index):
        print("name parser")
        print(name)
        if re.match("\s*not\s{1}.*", name):
            invert = True
        else:
            invert = False
        if re.match(".*resi\s{1}\d+$", name):
            resi = re.match(".*resi\s{1}(\d+)$", name).group(1)
            #resi_selector = "<ResidueIndex name=\"{}\" resnums=\"{}\">".format(selector_index, resi)
            #print(self.resi_selector)
            self.converted_lst.append(("Index", selector_index, resi, invert))
            #return resi_selector
        elif re.match(".*resi\s{1}\d+-\d+", name):
            g = re.match(".*resi\s{1}(\d+)-(\d+)", name)
            resi_1, resi_2 = g.group(1), g.group(2)
            #resi_selector = "<ResidueSpan name=\"{}\" resnums=\"{},{}\">".format(
            #    selector_index, resi_1, resi_2)
            self.converted_lst.append(("Index", selector_index, "{}-{}".format(resi_1, resi_2), invert))
            #print(resi_selector)
            #return resi_selector
        elif re.match(".*resn\s{1}\w+", name):
            resn = re.match(".*resn\s{1}(\w+)", name).group(1)
            #resn_selector = "<ResidueName name=\"{}\" residue_names=\"{}\">".format(selector_index, resn)
            #print(resn_selector)
            self.converted_lst.append(("ResidueName", selector_index, resn, invert))
            #return resn_selector
        elif re.match(".*chain\s{1}\w+", name):
            chain = re.match(".*chain\s{1}(\w+)", name).group(1)
            #chain_selector = "<Chain name=\"{}\" chains=\"{}\">".format(selector_index, chain)
            #print(chain_selector)
            self.converted_lst.append(("Chain", selector_index, chain, invert))
            #return chain_selector

    def get_list(self):
        print(self.converted_lst)
        return self.converted_lst



# <RESIDUE_SELECTORS>
# <ResidueName name="PTD_LYX" residue_names="PTD,LYX" />
# </RESIDUE_SELECTORS>
# <MOVE_MAP_FACTORIES>
# <MoveMapFactory name="fr_mm_factory" bb="0" chi="0">
# <Backbone residue_selector="PTD_LYX" />
# <Chi residue_selector="PTD_LYX" />
# </MoveMapFactory>
# </MOVE_MAP_FACTORIES>




#selection_string = "((a) and c)"
#ResidueSelection(selection_string)
