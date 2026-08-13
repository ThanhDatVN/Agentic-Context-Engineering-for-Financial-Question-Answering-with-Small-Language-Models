# Third-party notices

This repository contains or refers to third-party data, models, services, and software. Their terms apply independently of the ACE-FinQA repository license.

## FinQA

The files under `data/finqa/` originate from the official [FinQA repository](https://github.com/czyssrs/FinQA), which publishes the dataset and code under the MIT License. Cite Chen et al., *FinQA: A Dataset of Numerical Reasoning over Financial Data* (EMNLP 2021).

The upstream notice is reproduced below as required when redistributing the data:

> MIT License
>
> Copyright (c) 2021 Zhiyu Chen
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Models and libraries

The notebooks download or invoke Qwen/Unsloth model artifacts, PyTorch, Transformers, vLLM, Unsloth, sentence-transformers, and related packages. Model weights are not stored in this repository. Review the license and acceptable-use terms attached to the exact model revision and package version before downloading or redistributing them.

## OpenAI API

The ACE-FinQA thesis uses GPT-4o mini as a training-time Reflector. Use of that service is governed by the applicable OpenAI terms and policies. No API key is included in this repository.

## Thesis

`docs/thesis.pdf` is an original academic work by Lê Thành Đạt and is not covered by the FinQA MIT License. It remains All Rights Reserved unless the author states otherwise.
