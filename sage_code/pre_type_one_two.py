########################################################################
#                                                                      #
#                        PRE TYPE ONE TWO PRIMES                       #
#                                                                      #
########################################################################

import logging
from itertools import product

from sage.all import (
    ZZ,
    Integer,
    NumberField,
    gcd,
    lcm,
    matrix,
    prod,
)  # pylint: disable=no-name-in-module

from .character_enumeration import character_enumeration_filter
from .common_utils import R, get_weil_polys, gal_act_eps, eps_exp

logger = logging.getLogger(__name__)


def get_eps_type(eps):
    """Returns the type of an epsilon (quadratic, quartic, sextic), where
    an epsilon is considered as a tuple
    """

    if 6 in eps:
        if any(t in eps for t in [4, 8]):
            return "mixed"
        return "sextic"
    if any(t in eps for t in [4, 8]):
        if len(set(eps)) == 1:
            # means it's all 4s or all 8s
            return "quartic-diagonal"
        return "quartic-nondiagonal"
    return "quadratic"


def collapse_tuple(a_beta_tuple):

    a_beta_tuple_copy = list(a_beta_tuple).copy()
    beta_list = a_beta_tuple_copy
    output = beta_list.pop(0)
    while beta_list:
        output = output.tensor_product(beta_list.pop(0))
    return output


def get_redundant_epsilons(eps, galois_group=None):
    """Redundant epsilons are those in the dual orbits of a given
    epsilon. They are redundant because they yield the same ABC integers."""

    if galois_group:
        d = galois_group.order()
        G_action = (
            galois_group.as_finitely_presented_group()
            .as_permutation_group()
            .orbit(tuple(range(1, d + 1)), action="OnTuples")
        )

        redundant_epsilons = set()

        for sigma in G_action:
            eps_to_sigma = gal_act_eps(eps, sigma)
            redundant_epsilons.add(eps_to_sigma)
            eps_to_sigma_dual = tuple((12 - x) for x in eps_to_sigma)
            redundant_epsilons.add(eps_to_sigma_dual)
    else:
        redundant_epsilons = {eps, tuple((12 - x) for x in eps)}

    return redundant_epsilons


def remove_redundant_epsilons(epsilons, galois_group=None):

    epsilons_output = set()

    while epsilons:
        an_eps = epsilons.pop()
        eps_orbit = get_redundant_epsilons(
            an_eps, galois_group=galois_group
        )  # dual (and possibly Galois) orbit
        epsilons_output.add(an_eps)
        epsilons.difference_update(eps_orbit)

    return epsilons_output


def get_pre_type_one_two_epsilons(d, galgp=None, heavy_filter=False):
    """This method computes the epsilon group ring characters of Lemma 1 and
    Remark 1 of Momose. The three epsilons of type 1 and 2 are excluded.

    Args:
        d ([int]): Degree of the number field

    Returns:
        dictionary with keys a list of tuples defining the epsilon, and value
        the type of that epsilon
    """

    epsilons_dict = {}

    epsilons_keys = set(product([0, 4, 6, 8, 12], repeat=d))

    epsilons_keys -= {(0,) * d, (6,) * d, (12,) * d}  # remove types 1 and 2 epsilons

    logger.debug("epsilons before filtering: {}".format(len(epsilons_keys)))

    if not heavy_filter:
        epsilons_keys = remove_redundant_epsilons(epsilons_keys, galois_group=galgp)
        logger.debug("epsilons after filtering: {}".format(len(epsilons_keys)))
    else:
        logger.debug("Heavy filtering is on, so no epsilon filtering for now.")

    epsilons_dict = {eps: get_eps_type(eps) for eps in epsilons_keys}

    return epsilons_dict


def contains_imaginary_quadratic_field(K):
    """Choosing auxiliary primes in the PreTypeOneTwoCase requires us to
    choose non-principal primes if K contains an imaginary quadratic field."""

    K_deg_abs = K.absolute_degree()

    if K_deg_abs % 2 == 1:
        return (False, False)

    quadratic_subfields = K.subfields(2)

    imag_quad_subfields = [
        L for L, _, _ in quadratic_subfields if L.is_totally_imaginary()
    ]

    contains_hilbert_class_field_of_imag_quad = False

    for L in imag_quad_subfields:
        HL = L.hilbert_class_field("c")
        if HL.absolute_degree().divides(K.absolute_degree()):
            K_HL_composite = K.composite_fields(HL)[0]
            if K_HL_composite.absolute_degree() == K_deg_abs:
                contains_hilbert_class_field_of_imag_quad = True
                break

    return (bool(imag_quad_subfields), contains_hilbert_class_field_of_imag_quad)


def get_compositum(nf_list, maps=False):

    if len(nf_list) == 1:
        K = nf_list[0]
        return K, [K.hom(K)]

    nf_list_cp = nf_list.copy()

    running_compositum = nf_list_cp.pop(0)

    while nf_list_cp:
        other = nf_list_cp.pop(0)
        running_compositum = running_compositum.composite_fields(other)[0]

    # Now get the maps if requested

    if maps:
        maps_into_compositum = []

        for K in nf_list:
            K_into_comp = K.embeddings(running_compositum)[0]
            maps_into_compositum.append(K_into_comp)

        return running_compositum, maps_into_compositum

    return running_compositum


def filter_ABC_primes(K, prime_list, eps_type):
    """Apply congruence and splitting conditions to primes in prime
    list, depending on the type of epsilon

    Args:
        K ([NumberField]): our number field, assumed Galois
        prime_list ([list]): list of primes to filter
        eps_type ([str]): one of 'quadratic', 'quartic', or 'sextic'
    """

    if eps_type == "quadratic":
        # prime must split or ramify in K
        output_list = []

        for p in prime_list:
            if not K.ideal(p).is_prime():
                output_list.append(p)
        return output_list

    if eps_type == "quartic-nondiagonal":
        # prime must split or ramify in K, and be congruent to 2 mod 3
        output_list = []

        for p in prime_list:
            if p % 3 == 2:
                if not K.ideal(p).is_prime():
                    output_list.append(p)
        return output_list

    if eps_type == "quartic-diagonal":
        # prime must be congruent to 2 mod 3
        output_list = []

        for p in prime_list:
            if p % 3 == 2:
                output_list.append(p)
        return output_list

    if eps_type == "sextic":
        # prime must split or ramify in K, and be congruent to 3 mod 4
        output_list = []

        for p in prime_list:
            if p % 4 == 3:
                if not K.ideal(p).is_prime():
                    output_list.append(p)
        return output_list

    if eps_type == "mixed":
        # prime must split or ramify in K, and be congruent to 1 mod 12
        output_list = []

        for p in prime_list:
            if p % 12 == 1:
                if not K.ideal(p).is_prime():
                    output_list.append(p)
        return output_list

    raise ValueError("type must be quadratic, quartic, sextic, or mixed")


def get_aux_primes(K, norm_bound, C_K, h_K, contains_imaginary_quadratic):
    """Get the auxiliary primes, including the emergency aux primes"""

    aux_primes = K.primes_of_bounded_norm(norm_bound)
    completely_split_rat_primes = K.completely_split_primes(B=500)
    if contains_imaginary_quadratic:

        good_primes = [p for p in completely_split_rat_primes if gcd(p, 6 * h_K) == 1]
        list_of_gens = list(C_K.gens())
        i = 0
        while list_of_gens and (i < len(good_primes)):
            a_good_prime = good_primes[i]
            emergency_prime_candidates = K.primes_above(a_good_prime)

            for candidate in emergency_prime_candidates:
                emergency_gen = C_K(candidate)
                if emergency_gen in list_of_gens:
                    if a_good_prime > norm_bound:
                        aux_primes.append(candidate)
                        logger.debug("Emergency aux prime added: {}".format(candidate))
                    list_of_gens.remove(emergency_gen)
            i += 1

        if list_of_gens:
            raise RuntimeError(
                "We have been unable to add enough emergency "
                "auxiliary primes. Try increasing the `B` parameter above."
            )
    else:
        a_good_prime = completely_split_rat_primes[0]
        candidate = K.primes_above(a_good_prime)[0]
        if a_good_prime > norm_bound:
            aux_primes.append(candidate)
            logger.debug("Emergency aux prime added: {}".format(candidate))

    return aux_primes


def get_AB_integers(embeddings, frak_q, epsilons, q_class_group_order):

    output_dict_AB = {}
    alphas = (frak_q ** q_class_group_order).gens_reduced()
    assert len(alphas) == 1, "q^q_class_group_order not principal, which is very bad"
    alpha = alphas[0]
    nm_q = ZZ(frak_q.norm())
    for eps in epsilons:
        alpha_to_eps = eps_exp(alpha, eps, embeddings)
        A = (alpha_to_eps - 1).norm()
        B = (alpha_to_eps - (nm_q ** (12 * q_class_group_order))).norm()
        output_dict_AB[eps] = lcm(A, B)
    return output_dict_AB


def get_C_integers(
    K, embeddings, frak_q, epsilons, q_class_group_order, frob_polys_to_loop
):

    # Initialise output dict to empty sets
    output_dict_C = {}
    for eps in epsilons:
        output_dict_C[eps] = 1

    alphas = (frak_q ** q_class_group_order).gens_reduced()
    assert len(alphas) == 1, "q^q_class_group_order not principal, which is very bad"
    alpha = alphas[0]

    for frob_poly in frob_polys_to_loop:
        if frob_poly.is_irreducible():
            frob_poly_root_field = frob_poly.root_field("a")
        else:
            frob_poly_root_field = NumberField(R.gen(), "a")
        _, K_into_KL, L_into_KL, _ = K.composite_fields(
            frob_poly_root_field, "c", both_maps=True
        )[0]
        roots_of_frob = frob_poly.roots(frob_poly_root_field)
        betas = [r for r, e in roots_of_frob]

        for beta in betas:
            for eps in epsilons:
                # print('.', end='', flush=True)
                N = (
                    K_into_KL(eps_exp(alpha, eps, embeddings))
                    - L_into_KL(beta ** (12 * q_class_group_order))
                ).absolute_norm()
                N = ZZ(N)
                output_dict_C[eps] = lcm(output_dict_C[eps], N)
    return output_dict_C


def get_relevant_beta_mats(aux_primes, relevant_aux_prime_positions, frob_polys_dict):

    output_dict = {}
    for i in relevant_aux_prime_positions:
        do_stuff = [
            matrix.companion(a_frob_pol) ** 12
            for a_frob_pol in frob_polys_dict[aux_primes[i]]
        ]
        output_dict[aux_primes[i]] = do_stuff

    return output_dict


def get_PIL_integers(aux_primes, frob_polys_dict, Kgal, epsilons, embeddings, C_K):

    Lambda = principal_ideal_lattice(aux_primes, C_K)
    Lambda_basis = Lambda.basis()
    logger.debug("Lambda basis = {}".format(Lambda_basis))
    good_basis_elements = [v for v in Lambda_basis if len(v.nonzero_positions()) > 1]
    relevant_aux_prime_positions = {
        k for v in good_basis_elements for k in v.nonzero_positions()
    }
    relevant_beta_mats = get_relevant_beta_mats(
        aux_primes, relevant_aux_prime_positions, frob_polys_dict
    )

    alphas_dict = {}
    collapsed_beta_mats = {}
    for v in good_basis_elements:
        the_nonzero_positions = v.nonzero_positions()
        alphas = prod(
            [aux_primes[i] ** v[i] for i in the_nonzero_positions]
        ).gens_reduced()
        assert len(alphas) == 1, "uh oh"
        alphas_dict[v] = alphas[0]
        list_list_mats = [
            relevant_beta_mats[aux_primes[i]] for i in the_nonzero_positions
        ]
        beta_mat_tuples = list(product(*list_list_mats))
        # import pdb; pdb.set_trace()
        collapsed_beta_mats[v] = [
            collapse_tuple(a_beta_tuple) for a_beta_tuple in beta_mat_tuples
        ]
    logger.debug("Made the alphas and beta_mat_tuples")

    output_dict = {}
    how_many_eps = len(epsilons)
    i = 1
    for eps in epsilons:
        running_gcd = 0
        for v in good_basis_elements:
            running_lcm = 1
            for a_beta_mat in collapsed_beta_mats[v]:
                alpha_to_eps_mat = eps_exp(alphas_dict[v], eps, embeddings).matrix()
                pil_mat = alpha_to_eps_mat.tensor_product(a_beta_mat.parent()(1)) - (
                    alpha_to_eps_mat.parent()(1)
                ).tensor_product(a_beta_mat)
                pil_int = pil_mat.det()
                running_lcm = lcm(pil_int, running_lcm)
            running_gcd = gcd(running_lcm, running_gcd)
        output_dict[eps] = running_gcd
        logger.debug(
            "Successfully computed PIL int for {} epsilons. {} to go".format(
                i, how_many_eps - i
            )
        )
        i += 1
    return output_dict


def get_U_integers(K, epsilons, embeddings):
    """Get divisibilities from the units"""

    unit_gens = K.unit_group().gens_values()
    return {
        eps: gcd([(eps_exp(u, eps, embeddings) - 1).absolute_norm() for u in unit_gens])
        for eps in epsilons
    }


def as_ZZ_module(G, debug=False):
    """
    Input:
      - An abelian group G

    Output:
      - (H, Z, L) a tripple of ZZ-modules such that:
         1. H is isomorphic to G
         2. Z = ZZ^G.ngens()
         3. L is a submodule of Z such that Z/L=H
         4. The coordinates in H are such that
              G  -> H
              g |-> H(g.exponents())
            is an isomoprhism.
    """
    invs = list(reversed(G.elementary_divisors()))
    if debug:
        assert G.ngens() == len(invs)
        print(invs, [g.order() for g in G.gens()])
        for g, inv in zip(G.gens(), invs):
            assert g.order() == inv
    ZZn = ZZ ** len(invs)
    H = ZZn.submodule(ZZn.gen(i) * invs[i] for i in range(len(invs)))
    return ZZn / H, ZZn, H


def principal_ideal_lattice(aux_primes, class_group, debug=False):
    """
    Input:
      - aux_primes - a list of primes in a numberfield
      - class_group - the classgroup of the same numberfield
    Output:
      - The submodule of ZZ^aux_primes corresponding to the prinicpal ideals
    """
    C_ZZ_mod, C_num, C_den = as_ZZ_module(class_group)
    ZZt = ZZ ** len(aux_primes)
    if debug:
        for q in aux_primes:
            assert prod(
                g ^ i for g, i in zip(class_group.gens(), class_group(q).exponents())
            ) == class_group(q)
    phi = ZZt.hom(
        im_gens=[C_num(class_group(q).exponents()) for q in aux_primes], codomain=C_num
    )
    return phi.inverse_image(C_den)


def get_pre_type_one_two_primes(
    K, norm_bound=50, loop_curves=False, use_PIL=False, heavy_filter=False
):
    """Pre type 1-2 primes are the finitely many primes outside of which
    the isogeny character is necessarily of type 2 (or 3, which is not relevant
    for us)."""

    (
        contains_imaginary_quadratic,
        contains_hilbert_class_field,
    ) = contains_imaginary_quadratic_field(K)

    if contains_hilbert_class_field:
        raise ValueError(
            "The number field you entered contains the Hilbert "
            "Class field of an imaginary quadratic field. The set "
            "of isogeny primes in this case is therefore infinite."
        )

    # Set up important objects to be used throughout

    Kgal = K.galois_closure("b")
    C_K = K.class_group()
    h_K = C_K.order()
    aux_primes = get_aux_primes(K, norm_bound, C_K, h_K, contains_imaginary_quadratic)
    embeddings = K.embeddings(Kgal)

    # Generate the epsilons

    if K.is_galois():
        G_K = K.galois_group()
        epsilons = get_pre_type_one_two_epsilons(
            K.degree(), galgp=G_K, heavy_filter=heavy_filter
        )
    else:
        epsilons = get_pre_type_one_two_epsilons(K.degree(), heavy_filter=heavy_filter)

    # Now start with the divisibilities. Do the unit computation first

    divs_from_units = get_U_integers(K, epsilons, embeddings)
    logger.debug("Computed divisibilities from units")

    # Next do the computation of A,B and C integers

    tracking_dict = {}
    frob_polys_dict = {}

    for q in aux_primes:
        q_class_group_order = C_K(q).multiplicative_order()
        residue_field = q.residue_field(names="z")
        if loop_curves:
            frob_polys_to_loop = get_weil_polys(residue_field)
        else:
            frob_polys_to_loop = R.weil_polynomials(2, residue_field.cardinality())
        frob_polys_dict[q] = frob_polys_to_loop
        # these will be dicts with keys the epsilons, values sets of primes
        AB_integers_dict = get_AB_integers(embeddings, q, epsilons, q_class_group_order)
        C_integers_dict = get_C_integers(
            Kgal, embeddings, q, epsilons, q_class_group_order, frob_polys_to_loop
        )
        unified_dict = {}
        q_norm = Integer(q.norm())
        for eps in epsilons:
            unified_dict[eps] = gcd(
                lcm([q_norm, AB_integers_dict[eps], C_integers_dict[eps]]),
                divs_from_units[eps],
            )
        tracking_dict[q] = unified_dict
    logger.debug("Computed tracking dict")

    # Take gcds across all aux primes to get one integer for each epsilon

    tracking_dict_inv_collapsed = {}
    for eps in epsilons:
        q_dict = {}
        for q in aux_primes:
            q_dict[q] = tracking_dict[q][eps]
        q_dict_collapsed = gcd(list(q_dict.values()))
        tracking_dict_inv_collapsed[eps] = ZZ(q_dict_collapsed)

    # Optionally use the principal ideal lattice for further filtering

    if use_PIL and h_K > 1:
        logger.debug("Using PIL")
        PIL_integers_dict = get_PIL_integers(
            aux_primes, frob_polys_dict, Kgal, epsilons, embeddings, C_K
        )
        for eps in epsilons:
            tracking_dict_inv_collapsed[eps] = ZZ(
                gcd(tracking_dict_inv_collapsed[eps], PIL_integers_dict[eps])
            )

    # Split according to epsilon type, get prime divisors, and filter

    if heavy_filter:
        logger.debug("Using Heavy filtering")
        output = character_enumeration_filter(
            K, C_K, Kgal, tracking_dict_inv_collapsed, epsilons, aux_primes, embeddings
        )
        return output

    # Split according to epsilon type, get prime divisors, and filter

    final_split_dict = {}
    for eps_type in set(epsilons.values()):
        eps_type_tracking_dict_inv = {
            eps: ZZ(tracking_dict_inv_collapsed[eps])
            for eps in epsilons
            if epsilons[eps] == eps_type
        }
        eps_type_output = lcm(list(eps_type_tracking_dict_inv.values()))
        if eps_type_output.is_perfect_power():
            eps_type_output = eps_type_output.perfect_power()[0]
        eps_type_output = eps_type_output.prime_divisors()
        eps_type_output = filter_ABC_primes(Kgal, eps_type_output, eps_type)
        final_split_dict[eps_type] = set(eps_type_output)

    # Take union of all primes over all epsilons, sort, and return

    output = set.union(*(val for val in final_split_dict.values()))
    output = list(output)
    output.sort()
    return output
