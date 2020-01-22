#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""slim.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1plXbq5hAzXEE08leECNGFkiu6wgpNOwR

## Check env
"""

import argparse

parser = argparse.ArgumentParser()




""" argumentos"""

parser.add_argument("fila", help="path para a fila (pasta) de imagens. Ou uma imagem ")

parser.add_argument("interpolacoes", help="path para o diretorio do site com as interpolacoes a serem exibidas")

parser.add_argument("bkp_fila", help="path para a pasta contendo a imagens da fila que jah foram processadas")

parser.add_argument("--batch_fila", help="tamanho do batch da fila"
                                         "(qtd de imagens da fila a serem processadas por vez",
                    type=int, default=12)

parser.add_argument("--batch_net", help="tamanho do batch da rede "
                                        "(qtd de imagens da fila a serem processadas por vez",
                    type=int, default=6)

args = parser.parse_args()

"""## Dummy and standard values"""

"python process images/fila images/interpolacoes"

queue_dir = args.fila
out_dir = args.interpolacoes
done_dir= args.bkp_fila
queue_batch = args.batch_fila
net_batch = args.batch_net



# queue_dir = "fila"
# out_dir = "interpolacoes"
# done_dir= "processadas"
# net_batch = 2
# queue_batch = net_batch * 2

temp_dir = "/content/temp"
train_video = "True"

"""## Main code"""

import os, sys, numpy as np, shutil, subprocess
from pathlib import Path
from filelock import  FileLock
from subprocess import PIPE

def split_to_batches(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]

call_dir= Path.cwd()
root_dir= Path(sys.path[0]).absolute()
queue_dir = Path(queue_dir).absolute()
out_dir = Path(out_dir).absolute()
done_dir = Path(done_dir).absolute()
temp_dir = Path(root_dir/temp_dir).absolute()
train_video = False if train_video =="False" else True
call_dir, root_dir, queue_dir, out_dir, done_dir, temp_dir, train_video


lock = FileLock(root_dir / "gpu.lock")




"""### Chunk Loop"""

with lock.acquire(1):



  ###### looop
  #cria uma lista com um snapchot do glob

  #### if queue_dir is file chunk =[queue]



  if queue_dir.is_dir():
    queue = sorted(list(queue_dir.glob("*")) )
  else:
    queue = [queue_dir]



  for chunk in split_to_batches( queue, queue_batch):
    print("QUEUE CHUNCK:", chunk)
    print("net_batch", net_batch, "or len(chunk) if less")


    ##### limpa temp

    print("trying to delete temp")
    rm_ret = shutil.rmtree(temp_dir,
                  ignore_errors=True
                  )
    print("rmtree return:", rm_ret)

    temp_dir.mkdir();
    for name in ["raw_images", "aligned_images", "selected_images", "structured"]: (temp_dir / name).mkdir()

    # chunk = sorted(list(queue_dir.glob("*.jpg")))[:queue_batch]
    for f in chunk:
      shutil.copy(f,temp_dir/"raw_images")

    """## CD into Encoder folder and run"""

    os.chdir(root_dir/"stylegan-encoder")

    """#### Align"""

    import subprocess
    # p = subprocess.Popen(["python", "align_images.py", "raw_images/", "aligned_images/", "--output_size=1048"])
    # !python align_images.py /content/temp/raw_images/ /content/temp/aligned_images/ --output_size=1048
    p = subprocess.run(["python", "align_images.py", str(temp_dir/"raw_images"),
                        str(temp_dir/"aligned_images"), "--output_size=1048" ],
                      #  stdout=PIPE, stderr=PIPE,
                      )

    for f in chunk:
      shutil.copy( temp_dir/"aligned_images" / (f.stem+"_01.png"),  temp_dir/"selected_images")

    """#### Encode"""

    import subprocess

    # !python encode_images.py --batch_size=2 --output_video=True --load_resnet='data/finetuned_resnet.h5' --lr=0.01 --decay_rate=0.8 --iterations=200 --use_l1_penalty=0.3 /content/temp/selected_images/ /content/temp/generated_images/ /content/temp/latents/
    net_batch_i = net_batch if net_batch<= len(chunk) else len(chunk)

    p = subprocess.run(["python", "encode_images.py",
                        "--batch_size="+str(net_batch_i),
                        "--output_video="+str(train_video),
                        "--load_resnet='data/finetuned_resnet.h5'",
                        "--lr=0.01", "--decay_rate=0.8",
                        "--iterations=100", "--use_l1_penalty=0.3",
                        str(temp_dir/"selected_images"),
                        str(temp_dir/"generated_images"),
                        str(temp_dir/"latents")],
                      #  stdout=PIPE, stderr=PIPE,
                      )

    latents_list = [ np.load(path)  for path in sorted( temp_dir.glob("latents/*") ) ]
    np.save(temp_dir/"chunk_latents.npy", np.array(latents_list))

    """## CD to InterFaceGAN e interpola"""

    os.chdir(root_dir/"InterFaceGAN")

    semantics = ['age', 'eyeglasses', 'gender', 'pose', 'smile']
    ranges = [(-3.0,3.0), (0.0,1.0), (-1.0,1.0), (-0.5,0.8), (0.0,1.0), ]


    for trait, interval in zip(semantics, ranges):
      print("INTERPOLATING", trait+"...")
      p=subprocess.run(["python", "edit.py",
                      '-m', 'stylegan_ffhq',
                      '-b', 'boundaries/stylegan_ffhq_'+trait+'_w_boundary.npy',
                      '-s', "Wp",
                      '-i', str(temp_dir/'chunk_latents.npy'),
                      '-o', str(temp_dir/"interp_dump"/trait),
                      '--start_distance', str(interval[0]),
                      '--end_distance', str(interval[1]),
                      '--steps=48',
                      ],
                      # stdout=PIPE, stderr=PIPE,
                      )

    """## Move images"""

    os.chdir(root_dir)
    # os.chdir(root_dir/temp_dir)

    for i,f in zip (range(len(chunk)), chunk ):
      print ("organizing temporary file hierarchy")
      print(str(i).zfill(3),f)
      fdir = temp_dir/"structured"/f.stem
      os.mkdir(fdir)
      shutil.copy(f, fdir/(f.stem+"_original.png"))  ######## This one has to be copy here, not move
      shutil.copy(temp_dir/"selected_images"/(f.stem+"_01.png"), fdir/(f.stem+'.png'))
      shutil.copy(temp_dir/"generated_images"/(f.stem+"_01.png"), fdir/(f.stem+"_latent.png"))
      shutil.copy(temp_dir/"latents"/(f.stem+"_01.npy"), fdir/(f.stem+"_vector.npy"))
      for trait in semantics:
        os.mkdir(fdir/trait)
        for fj in (temp_dir/'interp_dump'/trait).glob('%03d_*'%i):
          shutil.copy(fj, fdir/trait)

    for f in (temp_dir/'structured').glob("*"):
      print(f"copying {f} to {out_dir/f.name}")
      shutil.copytree(f, out_dir/f.name)

    for f in chunk:
      shutil.move(f, done_dir/f.name)