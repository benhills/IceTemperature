#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 29 13:39:42 2019

@author: benhills
"""

import numpy as np
from scipy.interpolate import interp1d
from constants_stefan import constantsIceDiver
const = constantsIceDiver()

# -----------------------------------------------------------------------

# --- Dimensional Conversions --- #

def C_pbv(C,rho_solute):
    """
    Dimensional conversion from concentration (kg solute/m3 solution) to percent by volume (m3 solute/m3 solution)
    """
    pbv = C/rho_solute
    return pbv

def C_Molality(C,rho_solute,mmass_solute,const=const):
    """
    Dimensional conversion from concentration (kg solute/m3 solution) to molality (mole solute/kg solvent)
    """
    # calculate the density of the solution
    rhos = C + const.rhow*(1.-C/rho_solute)
    # calculate the molality of the solution (mole/kg)
    molality = 1000.*C/(mmass_solute*(rhos-C))
    return molality

def C_MoleFrac(C,rho_solute,mmass_solute,const=const):
    """
    Dimensional conversion from concentration (kg solute/m3 solution) to mole fraction (mole solute/mole solution)
    """
    # calculate the density of the solution
    rhos = C + const.rhow*(1.-C/rho_solute)
    # calculate the mole fraction
    hold = C*const.mmass_w/(mmass_solute*rhos)
    Xe = hold/(1.-C/rhos+hold)
    return Xe

def C_pbm(C,rho_solute,const=const):
    """
    Dimensional conversion from concentration (kg solute/m3 solution) to percent by mass (kg solute/kg solution)
    """
    rhos = C + const.rhow*(1.-C/rho_solute)
    pbm = C/rhos
    return pbm

def pbm_Molality(pbm,mmass_solute,const=const):
    """
    Dimensional conversion from percent by mass (kg solute/kg solution) to molality (mole solute/kg solvent)
    """
    top = pbm*1000./mmass_solute
    bottom = (1.-pbm)
    molality = top/bottom
    return molality

def pbm_C(pbm,rho_solute,const=const):
    """
    Dimensional conversion from percent by mass (kg solute/kg solution) to concentration (kg solute/m3 solution)
    """
    rhos = 1./((1./rho_solute)*pbm+(1./const.rhow)*(1.-pbm))
    C = pbm*rhos
    return C

# -----------------------------------------------------------------------

def molDiff(T,eta_s,r=.22e-9,const=const):
    """
    Stokes-Einstein relation for molecular diffusivity

    Parameters
    ----------
    C: float
        solution concentration
    T: float
        solution temperature
    r: float; optional
        particle radius
    const: class; optional

    Output
    ---------
    D: float
        molecular diffusivity
    """
    # if not in K, convert
    if T < 200:
        T += const.Tf0
    # Molecular diffusivity
    D = const.kBoltz*T/(6.*r*np.pi*eta_s)
    return D

def etaKhattab(Xe,T,const=const):
    """
    Aquous ethanol viscosity
    Approximated from  Khattab et al. 2012, eq. 6
    This was measured at warm temperatures (~293 K) but uses the Jouyban-Acree model
        with the vogel equation I extend to lower temps
    """

    # if not in K, convert
    if T < 200:
        T += const.Tf0
    # calculate water and ethanol viscosity (Vogel Equation)
    etaw = (1/1000.)*np.exp(-3.7188+(578.919/(-137.546+T)))
    etae = (1/1000.)*np.exp(-7.37146+(2770.25/(74.6787+T)))
    # Fraction water
    Xw = 1.-Xe
    # viscosity
    eta_s = np.exp(Xw*np.log(etaw)+Xe*np.log(etae)+\
            724.652*(Xw*Xe/T)+729.357*(Xw*Xe*(Xw-Xe)/T)+\
            976.050*(Xw*Xe*(Xw-Xe)**2./T))
    return eta_s

def Tf_depression(C,solvent='methanol',const=const):
    """
    Freezing point depression
    interpolated from empirical values in Industrial Solvents Handbook
    """

    if solvent=='methanol':
        # Get percent by mass
        PBM = C_pbm(C,const.rhom)
        # industrial solvents handbook, percent by mass
        Tfd = np.load('./methanol_freezingdepression_PBM.npy')
    elif solvent=='ethanol':
        # Get percent by mass
        PBM = C_pbm(C,const.rhoe)
        # industrial solvents handbook, percent by mass
        Tfd = np.load('./ethanol_freezingdepression_PBM.npy')
    # linear interpolation between points
    Tfd_interp = interp1d(Tfd[0], Tfd[1])
    Tf = Tfd_interp(PBM)
    return Tf

def Hmix(C,solvent='methanol',const=const):
    """
    # Enthalpy of mixing for aqueous ethanol
    Peeters and Huyskens (1993) Journal of Molecular Structure
    """
    # mole fraction
    Xe = C_MoleFrac(C)
    Xw = 1.-Xe
    if solvent=='methanol':
        c61 = -5.1
        c11 = -3.4
        c12 = 0.5
    elif solvent=='ethanol':
        c61 = -10.6
        c11 = -1.2
        c12 = 0.1
    H = 1000.*(c61*Xw**6.*Xe+c11*Xw*Xe+c12*Xw*Xe**2.)      # Enthalpy of mixing (J/mol); Peeters and Huyskens (1993) eq. 9
    phi = H*C/(const.mmass_e/1000.)                     # Energy density (J m-3)
    return H,phi
