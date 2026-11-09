'''Checks a domain and instance without running them.'''
import os
import tempfile


def check(domain: str, instance: str) -> str:
    '''Raises the error of pyRDDLGym if the RDDL texts have one, else returns a summary
    of the model, e.g. its numbers of grounded state and action fluents.'''
    from pyRDDLGym.core.env import RDDLEnv

    with tempfile.TemporaryDirectory() as folder:
        paths = [os.path.join(folder, name) for name in ('domain.rddl', 'instance.rddl')]
        for (path, text) in zip(paths, (domain, instance)):
            with open(path, 'w', encoding='utf-8') as file:
                file.write(text)
        env = RDDLEnv(*paths)
    try:
        model = env.model
        counts = [(len(model.ground_vars_with_values(fluents)), name)
                  for (fluents, name) in ((model.state_fluents, 'state'),
                                          (model.action_fluents, 'action'),
                                          (model.observ_fluents, 'observation'))]
        parts = [f'{count} {name}' for (count, name) in counts
                 if count or name != 'observation']
        return f'No errors · {model.domain_name} · {", ".join(parts)} fluents · ' \
               f'horizon {model.horizon}'
    finally:
        env.close()
