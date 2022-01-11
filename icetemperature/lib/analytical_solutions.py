#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Author:
Benjamin Hills
University of Washington
Earth and Space Sciences
Jan 5, 2022
"""

import numpy as np
from scipy.special import gamma as γ
from scipy.special import gammaincc as γincc
from scipy.special import erf
from scipy.integrate import quad
from scipy.special import lambertw
from constants import constants

from ice_properties import *

def Robin_T(m,const=constants(),melt=True,verbose=False):
    """
    Analytic ice temperature model from Robin (1955)

    Assumptions:
        1) no horizontal advection
        2) vertical advection is linear with depth
        3) firn column is treated as equivalent thickness of ice
        4) If base is warmer than the melting temperature recalculate with new basal gradient
        5) no strain heating

    Parameters
    ----------
    m:      class, Model
    const:  class,  Constants
    melt:   bool,   Choice to allow melting, when true the bed temperature
                    is locked at the pressure melting point and melt rates
                    are calculated
    verbose: bool, option to print all output

    Output
    ----------
    T:      1-D array,  Analytic solution for ice temperature
    """

    # Thermal diffusivity
    alpha = const.k/(const.rho*const.Cp)

    q2 = m.adot/(2*alpha*m.H)
    Tb_grad = -m.qgeo/const.k
    f = lambda z : np.exp(-(z**2.)*q2)
    TTb = Tb_grad*np.array([quad(f,0,zi)[0] for zi in m.z])
    dTs = m.Ts - TTb[-1]
    T = TTb + dTs
    # recalculate if basal temperature is above melting (see van der Veen pg 148)
    if melt and T[0] > m.pmp[0]:
        Tb_grad = -2.*np.sqrt(q2)*(m.pmp[0]-m.Ts)/np.sqrt(np.pi)*(np.sqrt(erf(m.adot*m.H/(2.*alpha)))**(-1))
        TTb = Tb_grad*np.array([quad(f,0,zi)[0] for zi in m.z])
        dTs = m.Ts - TTb[-1]
        T = TTb + dTs
        M = (Tb_grad + m.qgeo/const.k)*const.k/const.L
        if verbose:
            print('Melting at the bed: ', np.round(M*const.spy/const.rho*1000.,2), 'mm/year')
    if verbose:
        print('Finished Robin Solution for analytic temperature profile.\n')
    return T

# ---------------------------------------------------

def Rezvan_T(m,const=constants(),
             rate_factor=rate_factor,
             T_ratefactor=-10.,
             dHdx=0.,tau_dx=0.,
             gamma=1.397,gamma_plus=True,
             verbose=False):
    """
    1-D Analytical temperature profile from Rezvanbehbahani et al. (2019)
    Main improvement from the Robin (1955) solution is the nonlinear velocity profile

    Assumptions:
        1) no horizontal advection
        2) vertical advection takes the form v=(z/H)**(gamma)
        3) firn column is treated as equivalent thickness of ice
        TODO: 4) If base is warmer than the melting temperature recalculate with new basal gradient
        5) strain heating is added to the geothermal flux

    Parameters
    ----------
    m:      class, Model
    const:  class,  Constants
    rate_factor:     function, to calculate the rate factor from Glen's Flow Law
    T_ratefactor:   float, Temperature input to rate factor function (C)
    dHdx:       float, Surface slope to calculate tau_dx
    tau_dx:     float, driving stress input directly (Pa)
    gamma:      float, exponent on the vertical velocity
    gamma_plus: bool, optional to determine gama_plus from the logarithmic regression with Pe Number
    verbose: bool, option to print all output

    Output
    ----------
    T:      1-D array,  Analytic solution for ice temperature
    """

    # Thermal diffusivity
    alpha = const.k/(const.rho*const.Cp)
    if gamma_plus:
        # Solve for gamma using the logarithmic regression with the Pe number
        Pe = m.adot*m.H/alpha
        if Pe < 5. and verbose:
            print('Pe:',Pe)
            print('The gamma_plus fit is not well-adjusted for low Pe numbers.')
        # Rezvanbehbahani (2019) eq. (19)
        gamma = 1.39+.044*np.log(Pe)
    if dHdx != 0. and tau_dx == 0.:
        # driving stress Nye (1952)
        tau_dx = const.rho*const.g*H*abs(dHdx)
    if tau_dx != 0:
        # Energy from strain heating is added to the geothermal flux
        A = rate_factor(np.array([T_ratefactor]),const)[0]
        # Rezvanbehbahani (2019) eq. (22)
        qgeo_s = (2./5.)*A*m.H*tau_dx**4.
        qgeo = m.qgeo + qgeo_s
    # Rezvanbehbahani (2019) eq. (19)
    lamb = m.adot/(alpha*m.H**gamma)
    phi = -lamb/(gamma+1)

    # Rezvanbehbahani (2019) eq. (17)
    Γ_1 = γincc(1/(1+gamma),-phi*m.z**(gamma+1))*γ(1/(1+gamma))
    Γ_2 = γincc(1/(1+gamma),-phi*m.H**(gamma+1))*γ(1/(1+gamma))
    term2 = Γ_1-Γ_2
    T = m.Ts + m.qgeo*(-phi)**(-1./(gamma+1.))/(const.k*(gamma+1))*term2
    return T

# ---------------------------------------------------

def Meyer_T(m,const=constants(),
            rate_factor=rate_factor,
            T_bulk='average',
            Tb=0.,lam=0.,
            verbose=False):
    """
    Meyer and Minchew (2018)
    A 1-D analytical model of temperate ice in shear margins
    Uses the contact problem in applied mathematics

    Assumptions:
        1) horizontal advection is treated as an energy sink
        2) vertical advection is constant in depth (they do some linear analysis in their supplement)
        4) base is at the melting temperature
        5) Melting temperature is 0 through the column

    Parameters
    ----------
    m:          class,  Model
    const:      class,  Constants
    rateFactor: func,   function for the rate factor, A in Glen's Law
    T_ratefactor:   float, Temperature input to rate factor function (C)
    Tb:         float,  Basal temperature, at the pressure melting point
    lam:        float,  Paramaterized horizontal advection term
                        Meyer and Minchew (2018) eq. 11
    verbose: bool, option to print all output

    Output
    ----------
    T:      1-D array,  Analytic solution for ice temperature
    """

    # Calcualte an "average" temperature to use for temp-dependent constants
    if T_bulk == 'average':
        T_bulk = np.mean([m.Ts,m.pmp[0]])
    k = conductivity(T_bulk,const.rho)
    Cp = heat_capacity(T_bulk)
    # rate factor (Meyer uses 2.4e-24; Table 1)
    A = rate_factor(np.array([T_bulk]),const=const)[0]
    # Brinkman Number
    S = 2.*A**(-1./const.n)*(m.eps_xy)**((const.n+1.)/const.n)
    dT = Tb - m.Ts
    Br = (S*m.H**2.)/(k*dT)
    # Peclet Number
    Pe = (const.rho*Cp*m.adot*m.H)/(k)
    LAM = lam*m.H**2./(k*dT)
    if verbose:
        print('Meyer; Pe:', Pe,'Br:',Br)
    # temperature solution is different for diffusion only vs. advection-diffusion
    if abs(Pe) < 1e-3:
        # Critical Shear Strain
        eps_bar = (k*dT/(A**(-1/const.n)*m.H**(2.)))**(const.n/(const.n+1.))
        # Find the temperate thickness
        if m.eps_xy > eps_bar:
            hbar = 1.-np.sqrt(2./Br)
        else:
            hbar = 0.
        # Solve for the temperature profile
        T = m.Ts + dT*(Br/2.)*(1.-((m.z/m.H)**2.)-2.*hbar*(1.-m.z/m.H))
        T[m.z/H<hbar] = 0.
    else:
        # Critical Shear Strain
        eps_1 = (((0.5*Pe**2.)/(Pe-1.+np.exp(-Pe))+0.5*LAM)**(const.n/(const.n+1.)))
        eps_bar = eps_1 * ((k*dT/(A**(-1./const.n)*m.H**(2.)))**(const.n/(const.n+1.)))
        # Find the temperate thickness
        if m.eps_xy > eps_bar:
            h_1 = 1.-(Pe/(Br-LAM))
            h_2 = -(1./Pe)*(1.+np.real(lambertw(-np.exp(-(Pe**2./(Br-LAM))-1.))))
            hbar = h_1 + h_2
        else:
            hbar = 0.
        T = m.Ts + dT*((Br-LAM)/Pe)*(1.-m.z/m.H+(1./Pe)*np.exp(Pe*(hbar-1.))-(1./Pe)*np.exp(Pe*((hbar-m.z/m.H))))
        T[m.z/m.H<hbar] = 0.
    return T

# ---------------------------------------------------

def Perol_T(m,const=constants(),
                rate_factor=rate_factor,
                T_bulk='average',
                verbose=False):
    """
    Perol and Rice (2015)
    Analytic Solution for temperate ice in shear margins (equation #5)

    Assumptions:
        1) Bed is at the melting point
        2) All constants are temperature independent (rate factor uses T=-10)

    Parameters
    ----------
    m:          class,  Model
    const:      class,  Constants
    rateFactor: func,   function for the rate factor, A in Glen's Law
    T_bulk      float, Temperature input to the rate factor function, A(T)
    verbose: bool, option to print all output

    Output
    ----------
    T:          1-D array,  Analytic solution for ice temperature
    """

    # Calcualte an "average" temperature to use for temp-dependent constants
    if T_bulk == 'average':
        T_bulk = np.mean([m.Ts,m.pmp[0]])
    k = conductivity(T_bulk,const.rho)
    Cp = heat_capacity(T_bulk)
    A = rate_factor(np.array([T_bulk]),const=const)[0]
    # Peclet Number
    Pe = m.adot*m.H/(k/(const.rho*Cp))
    # Strain Heating
    S = 2.*A**(-1./const.n)*(m.eps_xy/2.)**((const.n+1.)/const.n)
    if verbose:
        print('Perol; A:',A, 'S:',S)
    # Empty Array for Temperatures, then loop through all z's
    T = np.empty_like(m.z)
    for i in range(len(m.z)):
        # Two functions to be integrated
        def f1(lam):
            return (1.-np.exp(-lam*Pe*m.z[i]**2./(2.*m.H**2.)))/(2.*lam*np.sqrt(1.-lam))
        def f2(lam):
            return (1.-np.exp(-lam*Pe/2.))/(2.*lam*np.sqrt(1.-lam))
        # Calculate temperature profile
        T[i] = m.pmp[0] + (m.Ts-m.pmp[0])*erf(np.sqrt(Pe/2.)*(m.z[i]/m.H))/erf(np.sqrt(Pe/2.)) - \
            S*m.H**2./(k*Pe) * (quad(f1,0.,1.)[0] - \
            (erf(np.sqrt(Pe/2.)*(m.z[i]/m.H))/erf(np.sqrt(Pe/2.))) * quad(f2,0.,1.)[0])
    return T
