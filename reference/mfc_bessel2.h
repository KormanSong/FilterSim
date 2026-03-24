#ifndef MFC_BESSEL2_H
#define MFC_BESSEL2_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

#ifndef MFC_BESSEL2_REAL_T
#define MFC_BESSEL2_REAL_T float
#endif

typedef struct
{
    /* configuration */
    MFC_BESSEL2_REAL_T fs_hz;
    MFC_BESSEL2_REAL_T cutoff_hz;

    /* normalized biquad coefficients:
       y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2] */
    MFC_BESSEL2_REAL_T b0;
    MFC_BESSEL2_REAL_T b1;
    MFC_BESSEL2_REAL_T b2;
    MFC_BESSEL2_REAL_T a1;
    MFC_BESSEL2_REAL_T a2;

    /* filter state */
    MFC_BESSEL2_REAL_T x1;
    MFC_BESSEL2_REAL_T x2;
    MFC_BESSEL2_REAL_T y1;
    MFC_BESSEL2_REAL_T y2;
    uint8_t primed;

    /* optional pointer binding for control-loop style usage */
    const volatile MFC_BESSEL2_REAL_T *input_ptr;
    volatile MFC_BESSEL2_REAL_T *output_ptr;
    const volatile MFC_BESSEL2_REAL_T *cutoff_ptr;
    MFC_BESSEL2_REAL_T last_cutoff_hz;
} mfc_bessel2_t;

void mfc_bessel2_init(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T fs_hz, MFC_BESSEL2_REAL_T cutoff_hz);
void mfc_bessel2_reset(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T init_value);
void mfc_bessel2_set_fs(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T fs_hz);
void mfc_bessel2_set_cutoff(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T cutoff_hz);
MFC_BESSEL2_REAL_T mfc_bessel2_process(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T x);

void mfc_bessel2_bind_input(mfc_bessel2_t *f, const volatile MFC_BESSEL2_REAL_T *input_ptr);
void mfc_bessel2_bind_output(mfc_bessel2_t *f, volatile MFC_BESSEL2_REAL_T *output_ptr);
void mfc_bessel2_bind_cutoff(mfc_bessel2_t *f, const volatile MFC_BESSEL2_REAL_T *cutoff_ptr);
MFC_BESSEL2_REAL_T mfc_bessel2_tick(mfc_bessel2_t *f);

#ifdef MFC_BESSEL2_IMPLEMENTATION

#include <math.h>

#ifndef MFC_BESSEL2_PI
#define MFC_BESSEL2_PI 3.14159265358979323846
#endif

#ifndef MFC_BESSEL2_Q
#define MFC_BESSEL2_Q 0.57735026919
#endif

#ifndef MFC_BESSEL2_MIN_CUTOFF_HZ
#define MFC_BESSEL2_MIN_CUTOFF_HZ 0.001
#endif

#ifndef MFC_BESSEL2_MAX_CUTOFF_RATIO
#define MFC_BESSEL2_MAX_CUTOFF_RATIO 0.45
#endif

static void mfc_bessel2_set_passthrough(mfc_bessel2_t *f)
{
    if (f == 0)
        return;

    f->b0 = (MFC_BESSEL2_REAL_T)1.0;
    f->b1 = (MFC_BESSEL2_REAL_T)0.0;
    f->b2 = (MFC_BESSEL2_REAL_T)0.0;
    f->a1 = (MFC_BESSEL2_REAL_T)0.0;
    f->a2 = (MFC_BESSEL2_REAL_T)0.0;
}

static MFC_BESSEL2_REAL_T mfc_bessel2_clamp_cutoff(MFC_BESSEL2_REAL_T fs_hz, MFC_BESSEL2_REAL_T cutoff_hz)
{
    MFC_BESSEL2_REAL_T max_cutoff;

    if (cutoff_hz < (MFC_BESSEL2_REAL_T)MFC_BESSEL2_MIN_CUTOFF_HZ)
        cutoff_hz = (MFC_BESSEL2_REAL_T)MFC_BESSEL2_MIN_CUTOFF_HZ;

    if (fs_hz <= (MFC_BESSEL2_REAL_T)0.0)
        return cutoff_hz;

    max_cutoff = fs_hz * (MFC_BESSEL2_REAL_T)MFC_BESSEL2_MAX_CUTOFF_RATIO;
    if (cutoff_hz > max_cutoff)
        cutoff_hz = max_cutoff;

    return cutoff_hz;
}

static void mfc_bessel2_update_coeff(mfc_bessel2_t *f)
{
    const MFC_BESSEL2_REAL_T q = (MFC_BESSEL2_REAL_T)MFC_BESSEL2_Q;
    MFC_BESSEL2_REAL_T fc;
    MFC_BESSEL2_REAL_T k;
    MFC_BESSEL2_REAL_T norm;

    if (f == 0)
        return;

    if (f->fs_hz <= (MFC_BESSEL2_REAL_T)0.0)
    {
        mfc_bessel2_set_passthrough(f);
        return;
    }

    fc = mfc_bessel2_clamp_cutoff(f->fs_hz, f->cutoff_hz);
    f->cutoff_hz = fc;

    k = (MFC_BESSEL2_REAL_T)tan((MFC_BESSEL2_REAL_T)(MFC_BESSEL2_PI * fc / f->fs_hz));
    norm = (MFC_BESSEL2_REAL_T)(
        ((MFC_BESSEL2_REAL_T)1.0) /
        (((MFC_BESSEL2_REAL_T)1.0) + (k / q) + (k * k))
    );

    f->b0 = (k * k) * norm;
    f->b1 = ((MFC_BESSEL2_REAL_T)2.0) * f->b0;
    f->b2 = f->b0;
    f->a1 = ((MFC_BESSEL2_REAL_T)2.0) * ((k * k) - ((MFC_BESSEL2_REAL_T)1.0)) * norm;
    f->a2 = (((MFC_BESSEL2_REAL_T)1.0) - (k / q) + (k * k)) * norm;
}

void mfc_bessel2_init(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T fs_hz, MFC_BESSEL2_REAL_T cutoff_hz)
{
    if (f == 0)
        return;

    f->fs_hz = fs_hz;
    f->cutoff_hz = cutoff_hz;

    f->b0 = (MFC_BESSEL2_REAL_T)0.0;
    f->b1 = (MFC_BESSEL2_REAL_T)0.0;
    f->b2 = (MFC_BESSEL2_REAL_T)0.0;
    f->a1 = (MFC_BESSEL2_REAL_T)0.0;
    f->a2 = (MFC_BESSEL2_REAL_T)0.0;

    f->x1 = (MFC_BESSEL2_REAL_T)0.0;
    f->x2 = (MFC_BESSEL2_REAL_T)0.0;
    f->y1 = (MFC_BESSEL2_REAL_T)0.0;
    f->y2 = (MFC_BESSEL2_REAL_T)0.0;
    f->primed = 0u;

    f->input_ptr = 0;
    f->output_ptr = 0;
    f->cutoff_ptr = 0;
    f->last_cutoff_hz = cutoff_hz;

    mfc_bessel2_update_coeff(f);
}

void mfc_bessel2_reset(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T init_value)
{
    if (f == 0)
        return;

    f->x1 = init_value;
    f->x2 = init_value;
    f->y1 = init_value;
    f->y2 = init_value;
    f->primed = 1u;
}

void mfc_bessel2_set_fs(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T fs_hz)
{
    if (f == 0)
        return;

    f->fs_hz = fs_hz;
    mfc_bessel2_update_coeff(f);
}

void mfc_bessel2_set_cutoff(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T cutoff_hz)
{
    if (f == 0)
        return;

    f->cutoff_hz = cutoff_hz;
    f->last_cutoff_hz = cutoff_hz;
    mfc_bessel2_update_coeff(f);
}

MFC_BESSEL2_REAL_T mfc_bessel2_process(mfc_bessel2_t *f, MFC_BESSEL2_REAL_T x)
{
    MFC_BESSEL2_REAL_T y;

    if (f == 0)
        return x;

    if (f->primed == 0u)
    {
        f->x1 = x;
        f->x2 = x;
        f->y1 = x;
        f->y2 = x;
        f->primed = 1u;
        return x;
    }

    y = (f->b0 * x)
      + (f->b1 * f->x1)
      + (f->b2 * f->x2)
      - (f->a1 * f->y1)
      - (f->a2 * f->y2);

    f->x2 = f->x1;
    f->x1 = x;
    f->y2 = f->y1;
    f->y1 = y;

    return y;
}

void mfc_bessel2_bind_input(mfc_bessel2_t *f, const volatile MFC_BESSEL2_REAL_T *input_ptr)
{
    if (f == 0)
        return;

    f->input_ptr = input_ptr;
}

void mfc_bessel2_bind_output(mfc_bessel2_t *f, volatile MFC_BESSEL2_REAL_T *output_ptr)
{
    if (f == 0)
        return;

    f->output_ptr = output_ptr;
}

void mfc_bessel2_bind_cutoff(mfc_bessel2_t *f, const volatile MFC_BESSEL2_REAL_T *cutoff_ptr)
{
    if (f == 0)
        return;

    f->cutoff_ptr = cutoff_ptr;
}

MFC_BESSEL2_REAL_T mfc_bessel2_tick(mfc_bessel2_t *f)
{
    MFC_BESSEL2_REAL_T x;
    MFC_BESSEL2_REAL_T y;

    if (f == 0)
        return (MFC_BESSEL2_REAL_T)0.0;

    if (f->cutoff_ptr != 0)
    {
        MFC_BESSEL2_REAL_T new_cutoff = *(f->cutoff_ptr);
        if (new_cutoff != f->last_cutoff_hz)
        {
            f->cutoff_hz = new_cutoff;
            f->last_cutoff_hz = new_cutoff;
            mfc_bessel2_update_coeff(f);
        }
    }

    if (f->input_ptr == 0)
        return f->y1;

    x = *(f->input_ptr);
    y = mfc_bessel2_process(f, x);

    if (f->output_ptr != 0)
        *(f->output_ptr) = y;

    return y;
}

#endif /* MFC_BESSEL2_IMPLEMENTATION */

#ifdef __cplusplus
}
#endif

#endif /* MFC_BESSEL2_H */
