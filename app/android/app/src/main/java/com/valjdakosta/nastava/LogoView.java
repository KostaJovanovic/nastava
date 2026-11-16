package com.valjdakosta.nastava;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PathMeasure;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.RectF;
import android.view.View;
import android.view.animation.PathInterpolator;

/**
 * The header logo drawing on, as on the site (pages/templates/base.html .brand__mark, style.css brand-draw): ring ->
 * line -> diagonal -> M, 1.65 s, cubic-bezier(.65, 0, .35, 1). The site's masks too: a line crossing over another
 * cuts a gap in it, drawing on with the crossing line; here each line is drawn on a layer and the cut strokes are
 * cleared out of it. In 40 units, the logo's own; the view is 64 across with the logo 12 in, the size the system
 * splash's icon has (288 dp, its middle 192 dp shows).
 */
public class LogoView extends View {

    static final long MS = 1650;

    private static final PathInterpolator EASE = new PathInterpolator(.65f, 0f, .35f, 1f);

    /** A stroke drawn on from its start: its path, width, delay and duration in s, and the site's --len for it. */
    private static final class Stroke {

        final float width, delay, dur, len;
        // Made once and reused: a new Path each frame made garbage collection stutter the animation.
        private final PathMeasure measure;
        private final Path out = new Path();

        Stroke(Path path, float width, float delay, float dur, float len) {
            this.measure = new PathMeasure(path, false);
            this.width = width;
            this.delay = delay;
            this.dur = dur;
            this.len = len;
        }

        /** Its drawn part at t s, as the site's dash (len long) shows it: offset from len + 2 (the 2 hides the round
         *  cap's dot) down to 0. The ring's len (99) is a little under its length, so it ends just short of closing,
         *  as on the site. */
        Path at(float t) {
            float p = EASE.getInterpolation(Math.max(0f, Math.min(1f, (t - delay) / dur)));
            float end = Math.min(p * (len + 2f) - 2f, len);
            out.rewind();
            if (end > 0f) measure.getSegment(0f, end, out, true);
            return out;
        }
    }

    private static Path ring() {
        // As SVG draws a rect (3, 11, 34 x 21.5, rx 6.5): from the top edge's start, clockwise.
        Path p = new Path();
        p.moveTo(9.5f, 11f);
        p.lineTo(30.5f, 11f);
        p.arcTo(new RectF(24f, 11f, 37f, 24f), -90f, 90f);
        p.lineTo(37f, 26f);
        p.arcTo(new RectF(24f, 19.5f, 37f, 32.5f), 0f, 90f);
        p.lineTo(9.5f, 32.5f);
        p.arcTo(new RectF(3f, 19.5f, 16f, 32.5f), 90f, 90f);
        p.lineTo(3f, 17.5f);
        p.arcTo(new RectF(3f, 11f, 16f, 24f), 180f, 90f);
        return p;
    }

    private static Path line(float x0, float y0, float x1, float y1) {
        Path p = new Path();
        p.moveTo(x0, y0);
        p.lineTo(x1, y1);
        return p;
    }

    private static Path m() {
        Path p = new Path();
        p.moveTo(4f, 29.6f);
        p.lineTo(4.8f, 27.8f);
        p.quadTo(10f, 16f, 17.3f, 7.8f);
        p.lineTo(15.5f, 30f);
        p.quadTo(24f, 14f, 33.4f, 4f);
        p.lineTo(26f, 34.5f);
        return p;
    }

    private static Path corner() {
        // The site's mark-x: M3 21V26a6.5 6.5 0 0 0 6.5 6.5, the ring's corner cutting the M (still, from the start).
        Path p = new Path();
        p.moveTo(3f, 21f);
        p.lineTo(3f, 26f);
        p.arcTo(new RectF(3f, 19.5f, 16f, 32.5f), 180f, -90f);
        return p;
    }

    // The lines and, per line, the cuts its mask has (the site's mark-s, -h, -m, -x).
    private static final Stroke RING = new Stroke(ring(), 1.5f, 0f, .7f, 99f);
    private static final Stroke H = new Stroke(line(.8f, 21.6f, 39.2f, 21.6f), 1.5f, .25f, .5f, 38.5f);
    private static final Stroke D = new Stroke(line(25f, 1f, 13f, 39f), 1.5f, .45f, .45f, 40f);
    private static final Stroke M = new Stroke(m(), 2.5f, .75f, .9f, 111f);
    private static final Stroke CUT_D = new Stroke(line(25f, 1f, 13f, 39f), 3f, .45f, .45f, 40f);
    private static final Stroke CUT_M = new Stroke(m(), 4f, .75f, .9f, 111f);
    private static final Stroke CUT_X = new Stroke(corner(), 3f, -1f, 1f, 99f); // not animated on the site: whole

    private static final Stroke[] LINES = { RING, H, D, M };
    private static final Stroke[][] CUTS = { { CUT_D }, { CUT_M, CUT_D }, { CUT_M }, { CUT_X } };

    private final Paint ink = paint(), cut = paint();
    private float t = 0f;
    private final ValueAnimator clock = ValueAnimator.ofFloat(0f, MS / 1000f).setDuration(MS);

    private static Paint paint() {
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeCap(Paint.Cap.ROUND);
        p.setStrokeJoin(Paint.Join.ROUND);
        return p;
    }

    public LogoView(Context context) {
        super(context);
        ink.setColor(0xFFFFFFFF);
        cut.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.CLEAR));
        clock.setInterpolator(null); // linear: each stroke eases on its own
        clock.addUpdateListener(a -> {
            t = (float) a.getAnimatedValue();
            invalidate();
        });
    }

    /** Draws on from the start; with the system's animations off, the finished logo at once. */
    public void start() {
        clock.start();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        float unit = Math.min(getWidth(), getHeight()) / 64f;
        canvas.save();
        canvas.translate((getWidth() - 64f * unit) / 2f + 12f * unit, (getHeight() - 64f * unit) / 2f + 12f * unit);
        canvas.scale(unit, unit);
        for (int i = 0; i < LINES.length; i++) {
            int layer = canvas.saveLayer(-12f, -12f, 52f, 52f, null);
            ink.setStrokeWidth(LINES[i].width);
            canvas.drawPath(LINES[i].at(t), ink);
            for (Stroke c : CUTS[i]) {
                cut.setStrokeWidth(c.width);
                canvas.drawPath(c.at(t), cut);
            }
            canvas.restoreToCount(layer);
        }
        canvas.restore();
    }
}
