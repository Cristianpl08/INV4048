import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from emotivead.contracts import emotion, reference_for, validate_segments
from emotivead.media import compose, ffmpeg, probe, run, silence_candidates


class Contracts(unittest.TestCase):
    def test_unicode_emotions_and_references(self):
        self.assertEqual(emotion('E\u0301xtasis'), 'Éxtasis')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'Sergio';folder.mkdir()
            (folder/'04 admiracion .wav').touch()
            self.assertEqual(reference_for(tmp,'Sergio','Admiración').name,'04 admiracion .wav')

    def test_reject_invalid_intervals(self):
        for start,end in [(-1,2),(2,1),(0,float('nan')),(0,11)]:
            with self.assertRaises(ValueError):
                validate_segments([{'start':start,'end':end,'text':'Hola.'}],10)
        with self.assertRaises(ValueError):
            validate_segments([{'start':0,'end':2,'text':'Hola.'},{'start':1,'end':3,'text':'Adiós.'}],10)
        with self.assertRaises(ValueError):
            validate_segments([{'id':'../escape','start':0,'end':2,'text':'Hola.'}],10)


class Media(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.video = self.root/'test.mp4'
        run([ffmpeg(),'-y','-v','error','-f','lavfi','-i','color=c=blue:s=160x120:r=25:d=4',
             '-f','lavfi','-i','sine=frequency=220:duration=4','-c:v','libx264','-c:a','aac',self.video])
        sr=24000
        sf.write(self.root/'voice.wav',.10*np.sin(2*np.pi*440*np.arange(sr)/sr),sr)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mix_preserves_timeline_and_ducks_only_selected_interval(self):
        result=compose(self.video,[{'id':'s1','start':1,'end':2.5,'text':'Texto','emotion':'Serenidad'}],
                       [self.root/'voice.wav'],self.root/'mix',duck_db=-14)
        ad,sr=sf.read(result['ad']);mixed,_=sf.read(result['mix']);base,_=sf.read(self.root/'mix'/'original.wav')
        self.assertLess(abs(probe(result['video'])['duration']-4),.05)
        self.assertEqual(len(ad),4*sr)
        self.assertLess(np.max(np.abs(ad[:sr])),.0001)
        self.assertLess(np.max(np.abs(mixed[:sr//2]-base[:sr//2])),.0001)
        # Subtract the known narration; original background is attenuated by ~14 dB.
        sl=slice(int(1.2*sr),int(1.8*sr))
        ratio=np.sqrt(np.mean((mixed[sl]-ad[sl])**2))/np.sqrt(np.mean(base[sl]**2))
        self.assertAlmostEqual(ratio,10**(-14/20),delta=.015)

    def test_refuse_overflow(self):
        with self.assertRaisesRegex(ValueError,'Acorta el texto'):
            compose(self.video,[{'id':'s1','start':1,'end':1.2,'text':'Texto'}],
                    [self.root/'voice.wav'],self.root/'overflow')

    def test_video_without_audio(self):
        silent=self.root/'silent.mp4'
        run([ffmpeg(),'-y','-v','error','-i',self.video,'-an','-c:v','copy',silent])
        self.assertEqual(len(silence_candidates(silent)),1)
        result=compose(silent,[{'id':'s1','start':1,'end':3,'text':'Texto'}],
                       [self.root/'voice.wav'],self.root/'silent_mix')
        self.assertTrue(Path(result['video']).exists())


if __name__=='__main__': unittest.main()
