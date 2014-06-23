# Copyright 2013 Novo Nordisk Foundation Center for Biosustainability,
# Technical University of Denmark.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Solver interface for the IBM ILOG CPLEX Optimization Studio solver.

Wraps the GLPK solver by subclassing and extending :class:`Model`,
:class:`Variable`, and :class:`Constraint` from :mod:`interface`.
"""

from warnings import warn

warn("Be careful! The CPLEX interface is still under construction ...")

import logging

log = logging.getLogger(__name__)
import types
import tempfile
import sympy
from sympy.core.add import _unevaluated_Add
from sympy.core.mul import _unevaluated_Mul
import cplex
import interface

_CPLEX_STATUS_TO_STATUS = {
    cplex.Cplex.solution.status.MIP_abort_feasible: interface.ABORTED,
    cplex.Cplex.solution.status.MIP_abort_infeasible: interface.ABORTED,
    cplex.Cplex.solution.status.MIP_dettime_limit_feasible: interface.TIME_LIMIT,
    cplex.Cplex.solution.status.MIP_dettime_limit_infeasible: interface.TIME_LIMIT,
    cplex.Cplex.solution.status.MIP_feasible: interface.FEASIBLE,
    cplex.Cplex.solution.status.MIP_feasible_relaxed_inf: interface.SPECIAL,
    cplex.Cplex.solution.status.MIP_feasible_relaxed_quad: interface.SPECIAL,
    cplex.Cplex.solution.status.MIP_feasible_relaxed_sum: interface.SPECIAL,
    cplex.Cplex.solution.status.MIP_infeasible: interface.INFEASIBLE,
    cplex.Cplex.solution.status.MIP_infeasible_or_unbounded: interface.INFEASIBLE_OR_UNBOUNDED,
    cplex.Cplex.solution.status.MIP_optimal: interface.OPTIMAL,
    cplex.Cplex.solution.status.MIP_optimal_infeasible: interface.SPECIAL,
    cplex.Cplex.solution.status.MIP_optimal_relaxed_inf: interface.SPECIAL,
    cplex.Cplex.solution.status.MIP_optimal_relaxed_sum: interface.SPECIAL,
    cplex.Cplex.solution.status.MIP_time_limit_feasible: interface.TIME_LIMIT,
    cplex.Cplex.solution.status.MIP_time_limit_infeasible: interface.TIME_LIMIT,
    cplex.Cplex.solution.status.MIP_unbounded: interface.UNBOUNDED,
    cplex.Cplex.solution.status.abort_dettime_limit: interface.ABORTED,
    cplex.Cplex.solution.status.abort_dual_obj_limit: interface.ABORTED,
    cplex.Cplex.solution.status.abort_iteration_limit: interface.ABORTED,
    cplex.Cplex.solution.status.abort_obj_limit: interface.ABORTED,
    cplex.Cplex.solution.status.abort_primal_obj_limit: interface.ABORTED,
    cplex.Cplex.solution.status.abort_relaxed: interface.ABORTED,
    cplex.Cplex.solution.status.abort_time_limit: interface.TIME_LIMIT,
    cplex.Cplex.solution.status.abort_user: interface.ABORTED,
    cplex.Cplex.solution.status.conflict_abort_contradiction: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_abort_dettime_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_abort_iteration_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_abort_memory_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_abort_node_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_abort_obj_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_abort_time_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_abort_user: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_feasible: interface.SPECIAL,
    cplex.Cplex.solution.status.conflict_minimal: interface.SPECIAL,
    cplex.Cplex.solution.status.fail_feasible: interface.SPECIAL,
    cplex.Cplex.solution.status.fail_feasible_no_tree: interface.SPECIAL,
    cplex.Cplex.solution.status.fail_infeasible: interface.SPECIAL,
    cplex.Cplex.solution.status.fail_infeasible_no_tree: interface.SPECIAL,
    cplex.Cplex.solution.status.feasible: interface.FEASIBLE,
    cplex.Cplex.solution.status.feasible_relaxed_inf: interface.SPECIAL,
    cplex.Cplex.solution.status.feasible_relaxed_quad: interface.SPECIAL,
    cplex.Cplex.solution.status.feasible_relaxed_sum: interface.SPECIAL,
    cplex.Cplex.solution.status.first_order: interface.SPECIAL,
    cplex.Cplex.solution.status.infeasible: interface.INFEASIBLE,
    cplex.Cplex.solution.status.infeasible_or_unbounded: interface.INFEASIBLE_OR_UNBOUNDED,
    cplex.Cplex.solution.status.mem_limit_feasible: interface.MEMORY_LIMIT,
    cplex.Cplex.solution.status.mem_limit_infeasible: interface.MEMORY_LIMIT,
    cplex.Cplex.solution.status.node_limit_feasible: interface.NODE_LIMIT,
    cplex.Cplex.solution.status.node_limit_infeasible: interface.NODE_LIMIT,
    cplex.Cplex.solution.status.num_best: interface.NUMERIC,
    cplex.Cplex.solution.status.optimal: interface.OPTIMAL,
    cplex.Cplex.solution.status.optimal_face_unbounded: interface.SPECIAL,
    cplex.Cplex.solution.status.optimal_infeasible: interface.SPECIAL,
    cplex.Cplex.solution.status.optimal_populated: interface.SPECIAL,
    cplex.Cplex.solution.status.optimal_populated_tolerance: interface.SPECIAL,
    cplex.Cplex.solution.status.optimal_relaxed_inf: interface.SPECIAL,
    cplex.Cplex.solution.status.optimal_relaxed_quad: interface.SPECIAL,
    cplex.Cplex.solution.status.optimal_relaxed_sum: interface.SPECIAL,
    cplex.Cplex.solution.status.optimal_tolerance: interface.SPECIAL,
    cplex.Cplex.solution.status.populate_solution_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.solution_limit: interface.SPECIAL,
    cplex.Cplex.solution.status.unbounded: interface.UNBOUNDED
}

_CPLEX_VTYPE_TO_VTYPE = {'C': 'continuous', 'I': 'integer', 'B': 'binary'}
# FIXME: what about 'S': 'semi_continuous', 'N': 'semi_integer'

_VTYPE_TO_CPLEX_VTYPE = dict(
    [(val, key) for key, val in _CPLEX_VTYPE_TO_VTYPE.iteritems()]
)


class Variable(interface.Variable):
    """CPLEX variable interface."""

    def __init__(self, name, *args, **kwargs):
        super(Variable, self).__init__(name, **kwargs)

    @interface.Variable.lb.setter
    def lb(self, value):
        super(Variable, self.__class__).lb.fset(self, value)
        self.problem.problem.variables.set_lower_bounds(self.name, value)

    @interface.Variable.ub.setter
    def ub(self, value):
        super(Variable, self.__class__).ub.fset(self, value)
        self.problem.problem.variables.set_upper_bounds(self.name, value)

    @interface.Variable.type.setter
    def type(self, value):
        try:
            cplex_kind = _VTYPE_TO_CPLEX_VTYPE[value]
        except KeyError:
            raise Exception("GLPK cannot handle variables of type %s. \
                        The following variable types are available:\n" +
                            " ".join(_VTYPE_TO_CPLEX_VTYPE.keys()))
        self.problem.problem.variables.set_types(self.name, cplex_kind)
        super(Variable, self).__setattr__(name, value)


    @property
    def primal(self):
        return self.problem.problem.solution.get_values(self.name)


    @property
    def dual(self):
        return self.problem.problem.solution.get_reduced_costs(self.name)


class Constraint(interface.Constraint):
    """GLPK solver interface"""

    def __init__(self, expression, *args, **kwargs):
        super(Constraint, self).__init__(expression, *args, **kwargs)

    @property
    def primal(self):
        return self.problem.problem.solution.get_dual_values(self.name)

    @property
    def dual(self):
        return self.problem.problem.solution.get_activity_levels(self.name)

    def __setattr__(self, name, value):

        super(Constraint, self).__setattr__(name, value)
        if getattr(self, 'problem', None):

            if name == 'name':

                self.problem._glpk_set_row_name(self)

            elif name == 'lb' or name == 'ub':
                self.problem._glpk_set_row_bounds(self)

            elif name == 'expression':
                pass


class Objective(interface.Objective):
    def __init__(self, *args, **kwargs):
        super(Objective, self).__init__(*args, **kwargs)

    @property
    def value(self):
        return self.problem.problem.solution.get_objective_value()

    def __setattr__(self, name, value):

        if getattr(self, 'problem', None):
            if name == 'direction':
                self.problem.problem.objective.set_sense(
                    {'min': self.problem.objective.sense.minimize, 'max': self.problem.objective.sense.maximize})
            super(Objective, self).__setattr__(name, value)
        else:
            super(Objective, self).__setattr__(name, value)


class Configuration(interface.MathematicalProgrammingConfiguration):
    def __init__(self, presolve=False, verbosity=0, *args, **kwargs):
        super(Configuration, self).__init__(*args, **kwargs)
        self._presolve = presolve
        self._verbosity = verbosity

    def __getstate__(self):
        return {'presolve': self.presolve, 'verbosity': self.verbosity}

    def __setstate__(self, state):
        self.__init__()
        for key, val in state.iteritems():
            setattr(self, key, val)

    @property
    def presolve(self):
        return self._presolve

    @presolve.setter
    def presolve(self, value):
        self._presolve = value

    @property
    def verbosity(self):
        return self._verbosity

    @verbosity.setter
    def verbosity(self, value):
        self._verbosity = value


class Model(interface.Model):
    def __init__(self, problem=None, *args, **kwargs):

        super(Model, self).__init__(*args, **kwargs)

        self.configuration = Configuration()

        if problem is None:
            self.problem = cplex.Cplex()

        elif isinstance(problem, cplex.Cplex):
            self.problem = problem
            zipped_var_args = zip(self.problem.variables.get_names(),
                                  self.problem.variables.get_lower_bounds(),
                                  self.problem.variables.get_upper_bounds()
            )
            for name, lb, ub in zipped_var_args:
                var = Variable(name, lb=lb, ub=ub, problem=self)
                super(Model, self)._add_variable(var)  # This avoids adding the variable to the glpk problem
            zipped_constr_args = zip(self.problem.linear_constraints.get_names(),
                                     self.problem.linear_constraints.get_rows(),
                                     self.problem.linear_constraints.get_senses(),
                                     self.problem.linear_constraints.get_rhs()

            )
            var = self.variables.values()
            for name, row, sense, rhs in zipped_constr_args:
                lhs = _unevaluated_Add(*[val * var[i - 1] for i, val in zip(row.ind, row.val)])
                if isinstance(lhs, int):
                    lhs = sympy.Integer(lhs)
                elif isinstance(lhs, float):
                    lhs = sympy.Real(lhs)
                if sense == 'E':
                    constr = Constraint(lhs, lb=rhs, ub=rhs, name=name, problem=self)
                elif sense == 'G':
                    constr = Constraint(lhs, lb=rhs, name=name, problem=self)
                elif sense == 'L':
                    constr = Constraint(lhs, ub=rhs, name=name, problem=self)
                elif sense == 'R':
                    range_val = self.problem.linear_constraints.get_rhs(name)
                    if range_val > 0:
                        constr = Constraint(lhs, lb=rhs, ub=rhs + range_val, name=name, problem=self)
                    else:
                        constr = Constraint(lhs, lb=rhs + range_val, ub=rhs, name=name, problem=self)
                else:
                    raise Exception, '%s is not a recognized constraint sense.' % sense
                super(Model, self)._add_constraint(
                    constr,
                    sloppy=True
                )
            self._objective = Objective(
                _unevaluated_Add(*[_unevaluated_Mul(sympy.Real(coeff), var[index]) for index, coeff in
                                   enumerate(self.problem.objective.get_linear()) if coeff != 0.]),
                problem=self,
                direction={self.problem.objective.sense.minimize: 'min', self.problem.objective.sense.maximize: 'max'}[
                    self.problem.objective.get_sense()],
                name=self.problem.objective.get_name()
            )
        else:
            raise Exception, "Provided problem is not a valid CPLEX model."

    def __getstate__(self):
        cplex_repr = self.__repr__()
        repr_dict = {'cplex_repr': cplex_repr}
        return repr_dict

    def __setstate__(self, repr_dict):
        tmp_file = tempfile.mktemp(suffix=".sav")
        open(tmp_file, 'w').write(repr_dict['cplex_repr'])
        problem = cplex.Cplex()
        problem.read(tmp_file)
        self.__init__(problem=problem)

    @property
    def objective(self):
        return self._objective

    @objective.setter
    def objective(self, value):
        super(Model, self.__class__).objective.fset(self, value)
        self._objective = value
        for i in xrange(len(self.problem.objective.get_linear())):
            self.problem.objective.set_linear(i, 0.)
        expression = self._objective.expression
        if isinstance(expression, types.FloatType) or isinstance(expression, types.IntType):
            pass
        else:
            if expression.is_Atom:
                self.problem.objective.set_linear(var.name, float(coeff))
            if expression.is_Mul:
                coeff, var = expression.args
                self.problem.objective.set_linear(var.name, float(coeff))
            elif expression.is_Add:
                for term in expression.args:
                    coeff, var = term.args
                    self.problem.objective.set_linear(var.name, float(coeff))
            else:
                raise ValueError(
                    "Provided objective %s doesn't seem to be appropriate." %
                    self._objective)
            self.problem.objective.set_sense(
                {'min': self.problem.objective.sense.minimize, 'max': self.problem.objective.sense.maximize}[
                    value.direction])

        value.problem = self

    def __str__(self):
        tmp_file = tempfile.mktemp(suffix=".lp")
        self.problem.write(tmp_file)
        cplex_form = open(tmp_file).read()
        return cplex_form

    def __repr__(self):
        tmp_file = tempfile.mktemp(suffix=".sav")
        self.problem.write(tmp_file)
        cplex_form = open(tmp_file).read()
        return cplex_form

    def optimize(self):
        self.problem.solve()
        cplex_status = self.problem.solution.get_status()
        self._status = _CPLEX_STATUS_TO_STATUS[cplex_status]
        return self.status

    def _cplex_sense_to_sympy(self, sense, translation={'E': '==', 'L': '<', 'G': '>'}):
        try:
            return translation[sense]
        except KeyError, e:
            print ' '.join('Sense', sense, 'is not a proper relational operator, e.g. >, <, == etc.')
            print e

    def _add_variable(self, variable):
        super(Model, self)._add_variable(variable)
        if variable.lb == None:
            lb = -cplex.infinity
        else:
            lb = variable.lb
        if variable.ub == None:
            ub = cplex.infinity
        else:
            ub = variable.ub
        vtype = _VTYPE_TO_CPLEX_VTYPE[variable.type]
        self.problem.variables.add([0.], lb=[lb], ub=[ub], types=[vtype], names=[variable.name])
        variable.problem = self
        return variable

    def _remove_variable(self, variable):
        super(Model, self)._remove_variable(variable)
        self.problem.variables.delete(variable.name)

    def _add_constraint(self, constraint, sloppy=False):
        if sloppy is False:
            if not (constraint.is_Linear or constraint.is_Quadratic):
                raise ValueError(
                    "CPLEX only supports linear or quadratic constraints. %s is neither linear nor quadratic." % constraint)
        super(Model, self)._add_constraint(constraint, sloppy=sloppy)

        for var in constraint.variables:
            if var.name not in self.variables:
                self._add_variable(var)

        if constraint.is_Linear:
            coeff_dict = constraint.expression.as_coefficients_dict()
            indices = [var.name for var in coeff_dict.keys()]
            values = [float(val) for val in coeff_dict.values()]
            if constraint.lb is None and constraint.ub is None:
                # FIXME: use cplex.infinity
                raise Exception("Free constraint ... %s" % constraint)
            elif constraint.lb is None:
                sense = 'L'
                rhs = float(constraint.ub)
                range_value = 0.
            elif constraint.ub is None:
                sense = 'G'
                rhs = float(constraint.lb)
                range_value = 0.
            else:
                sense = 'R'
                rhs = float(constraint.lb)
                range_value = float(constraint.ub - constraint.lb)
            self.problem.linear_constraints.add(
                lin_expr=[cplex.SparsePair(ind=indices, val=values)], senses=[sense], rhs=[rhs],
                range_values=[range_value], names=[constraint.name])
        constraint.problem = self
        return constraint

    def _remove_constraint(self, constraint):
        super(Model, self)._remove_constraint(constraint)
        if constraint.is_Linear:
            self.problem.linear_constraints.delete(constraint.name)
        elif constraint.is_Quadratic:
            self.problem.quadratic_constraints.delete(constraint.name)


if __name__ == '__main__':

    from optlang.cplex_interface import Model, Variable, Constraint, Objective

    x1 = Variable('x1', lb=0)
    x2 = Variable('x2', lb=0)
    x3 = Variable('x3', lb=0)
    c1 = Constraint(x1 + x2 + x3, ub=100, name='c1')
    c2 = Constraint(10 * x1 + 4 * x2 + 5 * x3, ub=600, name='c2')
    c3 = Constraint(2 * x1 + 2 * x2 + 6 * x3, ub=300, name='c3')
    obj = Objective(10 * x1 + 6 * x2 + 4 * x3, direction='max')
    model = Model(name='Simple model')
    model.objective = obj
    model.add([c1, c2, c3])
    print model
    status = model.optimize()
    print "status:", model.status
    print "objective value:", model.objective.value

    for var_name, var in model.variables.iteritems():
        print var_name, "=", var.primal


        # from cplex import Cplex
        # problem = Cplex()
        # problem.read("../tests/data/model.lp")

        # solver = Model(problem=problem)
        # print solver
        # solver.optimize()
        # print solver.objective.value
        # solver.add(z)
        # solver.add(constr)
        # # print solver
        # print solver.optimize()
        # print solver.objective