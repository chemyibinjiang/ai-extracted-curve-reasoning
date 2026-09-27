"""Independent checks of observations, reported errors and shared-family counts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import ROOT, LOG_BOUNDS, metrics, predict


def audit(output,source):
    read=lambda p: pd.read_csv(p,float_precision='round_trip')
    protocol=json.loads((output/'PROTOCOL.json').read_text())
    for name,expected in protocol['hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    original=read(source/'figure6/acid/POINT_PREDICTIONS.csv')
    fits=read(output/'CURVE_FITS.csv')
    original=original.set_index(['curve_uid','fit_point_index']).sort_index()
    assert original.index.is_unique and len(original)==1592
    for filename in ['POINT_PREDICTIONS.csv','HELDOUT_POINTS.csv']:
        frame=read(output/filename)
        for name,g in frame.groupby('model'):
            g=g.set_index(['curve_uid','fit_point_index']).sort_index()
            assert g.index.is_unique and g.index.equals(original.index)
            np.testing.assert_array_equal(g.eta_mV,original.eta_mV)
            np.testing.assert_array_equal(g.j_mA_cm2,original.j_mA_cm2)
            if filename=='POINT_PREDICTIONS.csv':
                rows=fits[fits.model.eq(name)].set_index('curve_uid')
                for uid,curve in g.groupby(level=0):
                    actual=metrics(curve.eta_mV,curve.prediction_mV)
                    for key in ['rmse','sse','r2']:
                        np.testing.assert_allclose(actual[key],rows.loc[uid,key],rtol=1e-10,atol=1e-9)
    # Independently optimize both Nernst parameters with a different algorithm.
    largest_gain=0.
    for row in fits[fits.model.eq('Nernst+jR')].itertuples():
        g=original.loc[row.curve_uid]
        j,y=g.j_mA_cm2.to_numpy(),g.eta_mV.to_numpy()
        start=np.array([row.log_jL,row.R])
        result=least_squares(lambda p:predict(j,dict(log_jL=p[0],R=p[1]))-y,start,
            bounds=([LOG_BOUNDS[0],0.],[LOG_BOUNDS[1],100.]),x_scale='jac',
            ftol=1e-12,xtol=1e-12,gtol=1e-10,max_nfev=1000)
        gain=row.sse-float(result.fun@result.fun)
        largest_gain=max(largest_gain,gain)
        assert gain < max(1e-6,1e-8*row.sse),(row.curve_uid,gain)
    pivot=fits.pivot(index='curve_uid',columns='model',values='sse')
    assert (pivot['Nernst+jR'] <= pivot['Nernst']+1e-7).all()
    assert (pivot['BV+jR'] <= pivot['BV']+1e-7).all()
    assignments=read(output/'NERNST_ASSIGNMENTS.csv')
    assert len(assignments)==73 and assignments.adequate.sum()==60
    for row in assignments.itertuples():
        curve=original.loc[row.curve_uid]
        yp=predict(curve.j_mA_cm2,dict(log_jL=np.log(row.beta),R=row.R))
        actual=metrics(curve.eta_mV,yp)
        np.testing.assert_allclose([row.rmse,row.r2],[actual['rmse'],actual['r2']],rtol=1e-10,atol=1e-9)
    report=dict(curves=73,points_per_model=1592,models=4,matching_original_observations=True,
        heldout_points_predicted_exactly_once=True,reported_metrics_recomputed=True,
        independent_optimizer_max_SSE_improvement=largest_gain,
        selected_library_count_verified=60,input_hashes_verified=True)
    (output/'AUDIT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/acid-nernst-control-20260927')
    parser.add_argument('--source',type=Path,default=ROOT/'build/effective-bv-20260927')
    args=parser.parse_args();audit(args.output,args.source)
