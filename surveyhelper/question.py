from itertools import compress
import pandas as pd
import numpy as np
from abc import ABCMeta, abstractmethod
from scipy.stats import ttest_ind, f_oneway, chisquare

class MatrixQuestion:
    __metaclass__ = ABCMeta

    def __init__(self, text, label, questions):
        self.text = text
        self.questions = questions
        self.label = label
        self.assert_questions_same_type()
        self.assert_choices_same()
        self.assign_children_to_matrix()

    def assert_questions_same_type(self):
        if all(type(x) == type(self.questions[0]) for x in self.questions):
            return(True)
        else:
            raise(Exception("Questions in a matrix must all have the same type"))

    def assert_choices_same(self):
        if all(x.same_choices(self.questions[0]) for x in self.questions):
            return(True)
        else:
            raise(Exception("Questions in a matrix must all have the same choices"))

    def assign_children_to_matrix(self):
        for q in self.questions:
            q.matrix = self
        return

    def get_variable_names(self):
        names = []
        for q in self.questions:
            names += q.get_variable_names()
        return(names)

    def get_children_text(self):
        return([q.text for q in self.questions])

    def pretty_print(self):
        print("{} ({})".format(self.text, self.label))
        self.questions[0].pretty_print_answers()
        for q in self.questions:
            print(q.text)

    @abstractmethod
    def get_choices(self):
        pass

    @abstractmethod
    def frequency_table(self):
        pass

class SelectOneMatrixQuestion(MatrixQuestion):

    def get_choices(self, remove_exclusions=True, show_values=False):
        self.assert_choices_same()
        return(self.questions[0].get_choices(remove_exclusions,
                                             show_values))

    def frequency_table(self, df, show="ct", pct_format=".0%",
                        remove_exclusions = True, show_totals=True, 
                        show_mean=True, mean_format=".1f"):
        data = []
        if show == "ct":
            for q in self.questions:
                data.append(q.frequency_table(df, False, True,
                            False, pct_format, remove_exclusions,
                            show_totals, show_mean,
                           ).iloc[:,0].tolist())
        elif show == "pct":
            for q in self.questions:
                data.append(q.frequency_table(df, False, False,
                            True, pct_format, remove_exclusions, 
                            show_totals, show_mean
                           ).iloc[:,0].tolist())
        else:
            raise(Exception("Invalid 'show' parameter: {}".format(show)))
        tbl = pd.DataFrame(data)
        tmpcols = self.get_choices(remove_exclusions, show_mean)

        if show_totals:
            tmpcols.append("Total")
        if show_mean:
            tmpcols.append("Mean")
        tbl.columns = tmpcols
        tbl["Question"] = self.get_children_text()
        cols = tbl.columns.tolist()
        cols = cols[-1:] + cols[:-1]
        tbl = tbl[cols]
        return(tbl)

    def cut_by_question(self, other_question, response_set, 
                        cut_var_label=None, question_labels=None,
                        pct_format=".0%", remove_exclusions=True, 
                        show_mean=True, mean_format=".1f"):
        if type(other_question) != SelectOneQuestion:
            raise(Exception("Can only call cut_by_question on a SelectOneQuestion type"))
        groups = response_set.groupby(other_question.label)
        group_mapping = dict(zip(other_question.values, other_question.choices))
        oth_text = cut_var_label
        if not oth_text:
            oth_text = other_question.text
        return(self.cut_by(groups, group_mapping, oth_text, question_labels,
               pct_format, remove_exclusions, show_mean, mean_format))

    def cut_by(self, groups, group_label_mapping, cut_var_label, 
               question_labels=None, pct_format=".0%",
               remove_exclusions=True, show_mean=True, mean_format=".1f"):

        results = []
        labels = question_labels
        if not labels:
            labels = [q.text for q in self.questions]
        for q, l in zip(self.questions, labels):
            r = q.cut_by(groups, group_label_mapping, cut_var_label,
                         l, pct_format, remove_exclusions, 
                         show_mean, mean_format)
            # r.columns = pd.MultiIndex.from_tuples([(q.text, b) for a, b in 
            #             r.columns.tolist()])
            results.append(r.T)
        return(pd.concat(results))



class SelectMultipleMatrixQuestion(MatrixQuestion):

    def get_choices(self, remove_exclusions=True):
        self.assert_choices_same()
        return(self.questions[0].get_choices(remove_exclusions))

    def frequency_table(self, df, show="ct", pct_format=".0%",
                        remove_exclusions = True, show_totals=True):
        data = []
        if show == "ct":
            for q in self.questions:
                data.append(q.frequency_table(df, False, True,
                            False, False, pct_format, remove_exclusions,
                            False).iloc[:,0].tolist())
        elif show == "pct_respondents":
            for q in self.responses:
                data.append(q.frequency_table(df, False, False, 
                            True, False, pct_format, remove_exclusions,
                            False).iloc[:,0].tolist())
        elif show == "pct_responses":
            for q in self.responses:
                data.append(q.frequency_table(df, False, False, 
                            False, True, pct_format, remove_exclusions,
                            False).iloc[:,0].tolist())
        else:
            raise(Exception("Invalid 'show' parameter: {}".format(show)))       
        tbl = pd.DataFrame(data)

        tbl.columns = self.get_choices(remove_exclusions)
        tbl["Question"] = self.get_children_text()
        cols = tbl.columns.tolist()
        cols = cols[-1:] + cols[:-1]
        tbl = tbl[cols]
        if show_totals:
            tots = []
            for q in self.questions:
                tots.append(q.get_total_respondents(df))
            tbl["Total Respondents"] = tots
        return(tbl)

class SelectQuestion:
    __metaclass__ = ABCMeta

    def get_total_respondents(self, df):
        freqs, resp, nonresp = self.tally(df)
        return(resp)

    @abstractmethod
    def get_choices(self):
        pass

    @abstractmethod
    def get_variable_names(self):
        pass

    @abstractmethod
    def pretty_print(self):
        pass

    @abstractmethod
    def pretty_print_answers(self):
        pass

    @abstractmethod
    def same_choices(self):
        pass

    @abstractmethod
    def tally(self):
        pass

    @abstractmethod
    def frequency_table(self):
        pass

class SelectOneQuestion(SelectQuestion):

    def __init__(self, text, var, choices, label, values, 
                 exclude_from_analysis, matrix=None):
        self.text = text
        # list of text choices in order
        self.choices = choices
        self.label = label
        self.variable = var
        self.values = values
        self.exclude_from_analysis = exclude_from_analysis
        self.matrix = matrix

    def get_variable_names(self):
        return([self.variable])

    def get_choices(self, remove_exclusions=True, show_values=False):
        choices = self.choices
        values = self.values
        if remove_exclusions:
            choices = list(compress(choices, 
                      [not x for x in self.exclude_from_analysis]))
            values = list(compress(values, 
                      [not x for x in self.exclude_from_analysis]))
        if show_values:
            if remove_exclusions:
                choices = ["{} ({})".format(c, v) for c, v in zip(choices, values)]
            else:
                new_choices = []
                for c, v, x in zip(choices, values, self.exclude_from_analysis):
                    if x:
                        new_choices.append("{} (X)".format(c))
                    else:
                        new_choices.append("{} ({})".format(c, v))
                choices = new_choices
        return(choices)

    def pretty_print(self):
        print("{} ({})".format(self.text, self.label))
        for a, b, c in zip(self.choices, self.values, 
                           self.exclude_from_analysis):
            if c:
                print("{} (X)".format(a))
            else:
                print("{} ({})".format(a, b))

    def pretty_print_answers(self):
        l = []
        for a, b, c in zip(self.choices, self.values, 
                           self.exclude_from_analysis):
            if c:
                l.append("{} (X)".format(a))
            else:
                l.append("{} ({})".format(a, b))
        print(", ".join(l))

    def same_choices(self, other):
        """
        Check to see if other has same choices as self
        """
        if ((self.choices == other.choices) and
           (self.values == other.values) and
           (self.exclude_from_analysis == other.exclude_from_analysis)):
            return(True)
        else:
            return(False)

    def mean(self, df, remove_exclusions=True):
        values = self.values
        if remove_exclusions:
            values = list(compress(values, 
                     [not x for x in self.exclude_from_analysis]))
        freq, n, x = self.tally(df, remove_exclusions)
        num = sum([ct * v for ct, v in zip(freq, values)])
        if n > 0:
            return(num/n)
        else:
            return(np.nan)

    def tally(self, df, remove_exclusions=True):
        """
        Returns ([response frequencies], respondents, nonrespondents) 
        tuple where response frequencies is a count of responses for 
        each answer choice in order.
        """
        unit_record = df[self.variable]
        freqs = dict(unit_record.value_counts())
        cts = []
        values = self.values
        if remove_exclusions:
            values = list(compress(values, 
                     [not x for x in self.exclude_from_analysis]))
        for k in values:
            if k in freqs:
                cts.append(freqs[k])
            else:
                cts.append(0)
        return((cts, sum(cts), len(unit_record)-sum(cts)))


    def frequency_table(self, df, show_question=True, ct=True, 
                        pct=True, pct_format=".0%", remove_exclusions=True,
                        show_totals=True, show_mean=True, mean_format=".1f"):
        cts, resp, nonresp = self.tally(df, remove_exclusions)
        data = []
        cols = []
        tots = []
        mean = []
        if show_question:
            data.append(self.get_choices(remove_exclusions, show_mean))
            cols.append("Answer")
            tots.append("Total")
            mean.append("Mean")
        if ct:
            data.append(cts)
            cols.append("Count")
            tots.append(resp)
            mean.append(format(self.mean(df, remove_exclusions), 
                        mean_format))
        if pct:
            l = []
            for x in cts:
                if resp > 0:
                    l.append(format(x/resp, pct_format))
                else:
                    l.append("-")
            data.append(l)
            cols.append("%")
            tots.append(format(1, pct_format))
            if not ct:
                mean.append(format(self.mean(df, remove_exclusions), 
                            mean_format))
            else:
                mean.append("")
        tbl = pd.DataFrame(data).T
        tbl.columns = cols
        if show_totals:
            tbl.loc[len(tbl)] = tots
        if show_mean:
            tbl.loc[len(tbl)] = mean
        return(tbl)

    def cut_by_question(self, other_question, response_set, 
                        cut_var_label=None, question_label=None,
                        pct_format=".0%", remove_exclusions=True, 
                        show_mean=True, mean_format=".1f"):
        if type(other_question) != SelectOneQuestion:
            raise(Exception("Can only call cut_by_question on a SelectOneQuestion type"))
        df = response_set.copy()
        # Here we remove the exclusions for the cut variable, the 
        # exclusions for this question are removed in cut_by, if 
        # appropriate
        if remove_exclusions:
            values_to_drop = [v for v, e in zip(other_question.values, 
                              other_question.exclude_from_analysis) if e]
            for v in values_to_drop:
                df[other_question.variable].replace(v, np.nan,
                                                      inplace=True)

        groups = df.groupby(other_question.label)
        group_mapping = dict(zip(other_question.values, other_question.choices))

        oth_text = cut_var_label
        if not oth_text:
            oth_text = other_question.text
        return(self.cut_by(groups, group_mapping, oth_text, question_label,
               pct_format, remove_exclusions, show_mean, mean_format))

    def cut_by(self, groups, group_label_mapping, cut_var_label, 
               question_label=None, pct_format=".0%",
               remove_exclusions=True, show_mean=True, mean_format=".1f"):

        freqs = []
        for k, gp in groups:
            t = (self.frequency_table(gp, True, False, True, pct_format,
                 remove_exclusions, False, show_mean, mean_format))
            t.set_index("Answer", inplace=True)
            series = t.ix[:,0]
            series.name = group_label_mapping[k]
            freqs.append(series)
        df = pd.DataFrame(freqs)

        if show_mean:
            if self.compare_groups(groups):
                df.columns = df.columns.tolist()[:-1] + \
                             [df.columns.tolist()[-1]+"*"]

        my_label = question_label
        if not my_label:
            my_label = self.text

        # Add hierarchical index to rows
        top_index = [cut_var_label]*len(groups)
        df.index = pd.MultiIndex.from_arrays([top_index, 
                   df.index.tolist()])

        # Add hierarchical index to columns
        col_top_index = [my_label]*len(self.choices)
        if show_mean:
            col_top_index += [my_label]
        df.columns = pd.MultiIndex.from_arrays([col_top_index, 
                     df.columns.tolist()])

        return(df)

    def compare_groups(self, groupby, pval = .05):
        data = [d[self.variable].dropna() for groupname, d in groupby]
        if len(groupby) == 2:
            ts, ps = ttest_ind(*data, equal_var=False)
            return(ps < pval)
        elif len(groupby.groups.keys()) == 2:
            # ANOVA
            f, p = f_oneway(*data)
            return(p < .05)
        else:
            return(False)

class SelectMultipleQuestion(SelectQuestion):

    def __init__(self, text, vars, choices, label, exclude_from_analysis,
                 matrix=None):
        self.text = text
        self.choices = choices
        self.label = label
        self.variables = vars
        self.exclude_from_analysis = exclude_from_analysis
        self.matrix = matrix

    def get_variable_names(self):
        return(self.variables)

    def get_choices(self, remove_exclusions=True):
        choices = self.choices
        if remove_exclusions:
            choices = list(compress(choices, 
                      [not x for x in self.exclude_from_analysis]))
        return(choices)

    def pretty_print(self):
        print("{} ({})".format(self.text, self.label))
        for a, b, c in zip(self.choices, self.variables, 
                           self.exclude_from_analysis):
            if c:
                print("{} (X)".format(a))
            else:
                print("{} ({})".format(a, b))


    def pretty_print_answers(self):
        l = []
        for a, b, c in zip(self.choices, self.variables, 
                           self.exclude_from_analysis):
            if c:
                l.append("{} (X)".format(a))
            else:
                l.append("{} ({})".format(a, b))
        print(", ".join(l))

    def same_choices(self, other):
        """
        Check to see if other has same choices as self
        """
        if ((self.choices == other.choices) and 
           (self.exclude_from_analysis == other.exclude_from_analysis)):
            return(True)
        else:
            return(False)

    def tally(self, df, remove_exclusions=True):
        """
        Returns (list, int1, int2) tuple where list is a count of
        responses for each answer choice. Int1 is the number of 
        respondents, and int2 is the number of nonrespondents.
        """
        vars = self.variables
        if remove_exclusions:
            vars = list(compress(vars, 
                   [not x for x in self.exclude_from_analysis]))
        unit_record = df[vars]
        nonrespondents = 0
        respondents = 0

        cts = [0]*len(vars)
        for index, row in unit_record.iterrows():
            if row.dropna().empty:
                nonrespondents += 1
            else:
                respondents += 1
                ct = 0
                for i, v in row.iteritems():
                    if not np.isnan(v):
                        cts[ct] += 1
                    ct += 1
        return(cts, respondents, nonrespondents)


    def frequency_table(self, df, show_question=True, ct=True, 
                        pct_respondents=True, pct_responses=False, 
                        pct_format=".0%", remove_exclusions=True,
                        show_totals=True):
        cts, resp, nonresp = self.tally(df, remove_exclusions)
        data = []
        cols = []
        tots = []
        if show_question:
            data.append(self.get_choices(remove_exclusions))
            cols.append("Answer")
            tots.append("Total respondents")
        if ct:
            data.append(cts)
            cols.append("Count")
            tots.append(resp)
        if pct_respondents:
            data.append([format(x/resp, pct_format) for x in cts])
            cols.append("% of respondents")
            tots.append("")
        if pct_responses:
            data.append([format(x/sum(cts), pct_format) for x in cts])
            cols.append("% of responses")
            tots.append("")
        tbl = pd.DataFrame(data).T
        tbl.columns = cols
        if show_totals:
            tbl.loc[len(tbl)] = tots
        return(tbl)


    def cut_by_question(self, other_question, response_set, 
                        cut_var_label=None, question_label=None,
                        pct_format=".0%", remove_exclusions=True, 
                        show_mean=True, mean_format=".1f"):
        if type(other_question) != SelectOneQuestion:
            raise(Exception("Can only call cut_by_question on a SelectOneQuestion type"))
        df = response_set.copy()
        # Here we remove the exclusions for the cut variable, the 
        # exclusions for this question are removed in cut_by, if 
        # appropriate
        if remove_exclusions:
            values_to_drop = [v for v, e in zip(other_question.values, 
                              other_question.exclude_from_analysis) if e]
            for v in values_to_drop:
                df[other_question.variable].replace(v, np.nan,
                                                      inplace=True)

        groups = df.groupby(other_question.label)
        group_mapping = dict(zip(other_question.values, other_question.choices))

        oth_text = cut_var_label
        if not oth_text:
            oth_text = other_question.text
        return(self.cut_by(groups, group_mapping, oth_text, question_label,
               pct_format, remove_exclusions))


    def cut_by(self, groups, group_label_mapping, cut_var_label, 
               question_label=None, pct_format=".0%",
               remove_exclusions=True):

        freqs = []
        for k, gp in groups:
            t = (self.frequency_table(gp, True, False, True, False, 
                 pct_format, remove_exclusions, False))
            t.set_index("Answer", inplace=True)
            series = t.ix[:,0]
            series.name = group_label_mapping[k]
            freqs.append(series)
        df = pd.DataFrame(freqs)

        my_label = question_label
        if not my_label:
            my_label = self.text

        # Add significance flags
        sigs = self.compare_groups(groups, remove_exclusions)
        newcols = []
        for s, i in zip(sigs, df.columns.tolist()):
            if s:
                newcols.append(i + "*")
            else:
                newcols.append(i)

        # Add hierarchical index to rows
        top_index = [cut_var_label]*len(groups)
        df.index = pd.MultiIndex.from_arrays([top_index, 
                   df.index.tolist()])

        # Add hierarchical index to columns
        col_top_index = [my_label]*len(self.choices)
        df.columns = pd.MultiIndex.from_arrays([col_top_index, 
                     newcols])

        return(df)

    def compare_groups(self, groupby, remove_exclusions=True, pval = .05):
        groupnames = groupby.groups.keys()
        obs_by_cut = []
        ct_by_cut = []
        for k, df in groupby:
            freqs, tot_resp, tot_nonresp = self.tally(df, remove_exclusions)
            obs_by_cut.append(freqs)
            ct_by_cut.append(tot_resp)
        choice_totals = [sum(x) for x in zip(*obs_by_cut)]
        exp_prop_per_choice = [t/sum(ct_by_cut) for t in choice_totals]
        sigs = []
        for f_obs, choice_tot, p_choice in zip(zip(*obs_by_cut), 
            choice_totals, exp_prop_per_choice):
            f_exp = [p_choice * ct for ct in ct_by_cut]
            chisq, p = chisquare(f_obs, f_exp)
            sigs.append(p < pval)
        print("sigs is {}".format(sigs))
        return(sigs)
