#Copyright 2021 Georg Kempf, Friedrich Miescher Institute for Biomedical Research
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.
import re
from pyparsing import ParseException, Word, printables, infixNotation, Group, alphas, nums, White, opAssoc
import sys
import logging


logger = logging.getLogger("RosEM")

class SelectionParserError(Exception):
    pass

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
        logger.debug("Selection string")
        logger.debug(self.selection_string)
        self.ops = ['and', 'or']
        self.selector_lst = []
        self.converted_lst = []
        self.remove_quotes()
        self.add_parantheses()
        self.selection_lst = self.parse_nested_expr()
        self.replace_name(self.selection_lst)
        self.replace_op(self.selection_lst)
        self.reorder_by_selector_index()
        self.index_dict = {}
        self.error_msg = []

    def remove_quotes(self):
        if re.search('"', self.selection_string):
            logger.debug("removing quotes")
            self.selection_string = self.selection_string.replace('"', '')


    def add_parantheses(self):
        if not self.selection_string.startswith("("):
            self.selection_string = "({}".format(self.selection_string)
        if not self.selection_string.endswith(")"):
            self.selection_string = "{})".format(self.selection_string)

    def parse_nested_expr(self):
        varname = Word(alphas + nums + "-")
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
            logger.debug("exception parsing selection string")
            comparisonExpr = Group(term + comparisonOp + term + comparisonOp + term)
            #comparisonExpr = Group(term)
            logicalExpr = infixNotation(comparisonExpr,
                                        [
                                            ('and', 2, opAssoc.LEFT),
                                            ('or', 2, opAssoc.LEFT),
                                        ])
            result = logicalExpr.parseString(self.selection_string).asList()
        logger.debug("nested_expr")
        logger.debug(result)
        logger.debug(self.selection_string)
        return result

    def replace_name(self, lst, indices=[], prev_i=-1):
        for i, item in enumerate(lst):
            if i == 0:
                indices.append(i)
            logger.debug("Item: {}, Index: {}".format(item, i))
            if isinstance(item, list):
                indices[-1] = i
                logger.debug("new indices list: {}".format(indices))
                self.replace_name(item, indices)
            else:
                if not item in self.ops and not item is None:
                    if i == 0:
                        logger.debug(lst)
                        merged = ''.join([str(x) for x in lst])
                        logger.debug("merged")
                        logger.debug(merged)
                        selector_index = ''.join([str(x) for x in indices])
                        selector = self.name_parser(merged, selector_index)
                        lst[:] = [selector]
                        self.selector_lst.append(selector)
                    else:
                        logger.debug("delete {}".format(i))
                        #del lst[i]
            if i + 1 == len(lst):
                indices.pop()
            prev_i = i

    def replace_op(self, lst, indices=[]):
        op_found = False
        for i, item in enumerate(lst):

            if i == 0:
                indices.append(i)
            logger.debug("Item: {}, Index: {}".format(item, i))
            if isinstance(item, list):

                indices[-1] = i
                logger.debug("new indices list: {}".format(indices))
                ops = set([x for x in item if x in self.ops])
                #If list element does not contain any further nested expressions do not reset op_found
                if len(ops) > 0:
                    op_found = False
                self.replace_op(item, indices)
            elif not op_found:
                selector_index = ''.join([str(x) for x in indices]) + '0'
                indices[-1] = i
                if not item is None:
                    if item.lower() in self.ops:
                        logger.debug("All elements")
                        num_elements = len([x for x in lst if not x in self.ops])
                        all_elements = [''.join([str(x) for x in indices[:-1]]) + str(o) + '0' for o in range(0, (num_elements*2), 2)]
                        logger.debug(all_elements)
                        logger.debug(indices)
                        if item.lower() == 'and':
                            self.converted_lst.append(
                                ("And", selector_index[:-1], ','.join(x for x in all_elements), False)
                            )
                            op_found = True
                        elif item.lower() == 'or':
                            self.converted_lst.append(
                                ("Or", selector_index[:-1], ','.join(x for x in all_elements), False)
                            )
                            op_found = True
                        else:
                            logger.debug("delete {}".format(i))
            if i + 1 == len(lst):
                indices.pop()
            prev_i = i

    def name_parser(self, name, selector_index):
        logger.debug("name parser")
        logger.debug(name)
        if re.match("\s*not\s{1}.*", name):
            invert = True
        else:
            invert = False
        if re.match(".*resi\s{1}\w+$", name):
            resi = re.match(".*resi\s{1}(\w+)$", name).group(1)
            self.converted_lst.append(("Index", selector_index, resi, invert))
        elif re.match(".*resi\s{1}\w+-\w+", name):
            logger.debug("resi match")
            g = re.match(".*resi\s{1}(\w+)-(\w+)", name)
            resi_1, resi_2 = g.group(1), g.group(2)
            self.converted_lst.append(("Index", selector_index, "{}-{}".format(resi_1, resi_2), invert))
        elif re.match(".*resn\s{1}\w+", name):
            resn = re.match(".*resn\s{1}(\w+)", name).group(1)
            self.converted_lst.append(("ResidueName", selector_index, resn, invert))
        elif re.match(".*chain\s{1}\w+", name):
            chain = re.match(".*chain\s{1}(\w+)", name).group(1)
            self.converted_lst.append(("Chain", selector_index, chain, invert))

    def reorder_by_selector_index(self):
        prev_num = 0
        prev_index = 0
        reordered = True
        if len(self.converted_lst) > 1:
            while reordered:
                for i, item in enumerate(self.converted_lst):
                    num = item[1].lstrip("0")
                    num = 0 if len(num) == 0 else num
                    if not i == 0:
                        if len(item[1]) > len(prev_index_name):
                            logger.debug(f"{item[1]} shorter than {prev_index_name}")
                            item_pop = self.converted_lst.pop(i)
                            self.converted_lst.insert(i-1, item_pop)
                            reordered = True
                        elif len(item[1]) == len(self.converted_lst[prev_index][1]):
                            if int(num) > int(prev_num):
                                item_pop = self.converted_lst.pop(i)
                                self.converted_lst.insert(i-1, item_pop)
                                reordered = True
                        else:
                            reordered = False
                    prev_num = num
                    prev_index_name = item[1]
                    logger.debug("Reorder")
                    logger.debug(self.converted_lst)

    def get_list(self):
        if self.error_msg != []:
            raise SelectionParserError(' '.join(self.error_msg))
            return self.error_msg
        else:
            logger.debug(self.converted_lst)
            return self.converted_lst

def main():
    logger = logging.getLogger('RosEM')
    formatter = logging.Formatter("[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ResidueSelection(sys.argv[1]).get_list()

if __name__ == '__main__':
    main()
