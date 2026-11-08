import os
import re
import tempfile
import unittest
import warnings

import pyRDDLGym

from rddl_ide.core.errorlocation import locate_error

DOMAIN = '''// a domain with comments and blank lines, which the parser does not see

domain counters {

    // the types
    types {
        cell : object;
    };

    pvariables {
        LIMIT(cell) : { non-fluent, int, default = 3 };   // trailing comment
        count(cell) : { state-fluent, int, default = 0 };
        other(cell) : { state-fluent, int, default = 0 };
        bump(cell) : { action-fluent, bool, default = false };
    };

    cpfs {

        count'(?c) = if (bump(?c))
                     then count(?c) + 1
                     else count(?c);

        other'(?c) = if (bump(?c))
                     then count(?c) + 1
                     else count(?c);
    };

    reward = sum_{?c : cell} [count(?c)];

    action-preconditions {
        forall_{?c : cell} [count(?c) <= LIMIT(?c)];
        forall_{?c : cell} [other(?c) <= LIMIT(?c)];
    };
}
'''

INSTANCE = '''non-fluents counters_nf {
    domain = counters;
    objects {
        cell : {c1, c2};
    };
}

// the instance
instance counters_inst {
    domain = counters;
    non-fluents = counters_nf;
    max-nondef-actions = 1;
    horizon = 5;
    discount = 1.0;
}
'''


def error_of(domain, instance):
    '''The message of the error pyRDDLGym raises for the given sources.'''
    with tempfile.TemporaryDirectory() as folder:
        paths = [os.path.join(folder, name) for name in ('domain.rddl', 'instance.rddl')]
        for (path, text) in zip(paths, (domain, instance)):
            with open(path, 'w') as file:
                file.write(text)
        try:
            pyRDDLGym.make(domain=paths[0], instance=paths[1])
        except Exception as error:
            return str(error)
    raise AssertionError('pyRDDLGym raised no error')


def text_at(text, location):
    '''The text between two Tk indices.'''
    lines = text.split('\n')
    (l1, c1), (l2, c2) = (map(int, index.split('.')) for index in (location.start, location.end))
    if l1 == l2:
        return lines[l1 - 1][c1:c2]
    return '\n'.join([lines[l1 - 1][c1:]] + lines[l1:l2 - 1] + [lines[l2 - 1][:c2]])


class TestErrorLocation(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings('ignore')

    def locate(self, domain=DOMAIN, instance=INSTANCE):
        location = locate_error(error_of(domain, instance), domain, instance)
        self.assertIsNotNone(location)
        return location

    def test_sources_are_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [os.path.join(folder, name) for name in ('d.rddl', 'i.rddl')]
            for (path, text) in zip(paths, (DOMAIN, INSTANCE)):
                with open(path, 'w') as file:
                    file.write(text)
            pyRDDLGym.make(domain=paths[0], instance=paths[1])

    def test_syntax_error_line_despite_comments(self):
        domain = DOMAIN.replace('else count(?c);\n\n', 'else count(?c) +;\n\n', 1)
        location = self.locate(domain)
        self.assertEqual(location.source, 'domain')
        self.assertEqual(location.start, '21.21')
        self.assertEqual(text_at(domain, location), 'else count(?c) +;')

    def test_syntax_error_on_a_repeated_line(self):
        # without the ; the parser fails at the '};' closing cpfs, one of four '};'
        domain = DOMAIN.replace('else count(?c);\n    };', 'else count(?c)\n    };')
        location = self.locate(domain)
        self.assertEqual((location.start, location.end), ('26.4', '26.6'))

    def test_syntax_error_line_number_is_not_needed(self):
        domain = DOMAIN.replace('else count(?c);\n    };', 'else count(?c)\n    };')
        message = re.sub(r'line \d+', 'line 1', error_of(domain, INSTANCE))
        self.assertEqual(locate_error(message, domain, INSTANCE).start, '26.4')

    def test_syntax_error_in_instance(self):
        instance = INSTANCE.replace('horizon = 5;', 'horizon horizon = 5;')
        location = self.locate(instance=instance)
        self.assertEqual(location.source, 'instance')
        self.assertEqual(text_at(instance, location), 'horizon horizon = 5;')

    def test_syntax_error_excludes_trailing_comment(self):
        domain = DOMAIN.replace('default = 3 };', 'default = 3 }', 1)
        location = self.locate(domain)
        text = text_at(domain, location)
        self.assertNotIn('//', text)
        self.assertEqual(text, text.strip())

    def test_expression_in_the_cpf_named_by_the_error(self):
        # the faulty expression is in both cpfs, but only other' is broken
        domain = DOMAIN.replace("other'(?c) = if (bump(?c))", "other'(?c) = if (bump(?c, ?c))")
        location = self.locate(domain)
        self.assertEqual(location.source, 'domain')
        self.assertEqual(text_at(domain, location), 'bump(?c, ?c)')
        self.assertEqual(location.start.split('.')[0], '23')

    def test_expression_in_numbered_precondition(self):
        domain = DOMAIN.replace('[other(?c) <= LIMIT(?c)]', '[other(?c) <= LIMIT(?c, ?c)]')
        location = self.locate(domain)
        self.assertEqual(text_at(domain, location), 'LIMIT(?c, ?c)')
        self.assertEqual(location.start.split('.')[0], '32')

    def test_multiline_expression_with_other_whitespace(self):
        message = ('Operator + can not be applied.\n'
                   '>> if (bump(?c)) then (count(?c) + 1) else count(?c)\n'
                   "Please check expression for CPF other'.")
        location = locate_error(message, DOMAIN, INSTANCE)
        self.assertEqual(location.source, 'domain')
        self.assertTrue(location.start.startswith('23.'))
        self.assertTrue(text_at(DOMAIN, location).startswith('if (bump(?c))'))
        self.assertTrue(text_at(DOMAIN, location).endswith('else count(?c)'))

    def test_no_highlight_without_location(self):
        self.assertIsNone(locate_error('Variable <x> is not defined.', DOMAIN, INSTANCE))

    def test_no_highlight_for_unrelated_expression(self):
        message = '>> completely_unrelated_function_name(?zz, ?yy, ?xx)'
        self.assertIsNone(locate_error(message, DOMAIN, INSTANCE))


if __name__ == '__main__':
    unittest.main()
