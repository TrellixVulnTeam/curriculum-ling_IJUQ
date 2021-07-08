import os
import torch
import utils
import numpy as np
from tqdm import tqdm
from transformers import BertTokenizer


def extract(args, model, loader, output_path):
    model.eval()
    os.makedirs(output_path, exist_ok=True)
    extraction_path = os.path.join(output_path, "extraction.txt")
    tokenizer = BertTokenizer.from_pretrained(args.bert_config)
    file = open(extraction_path, 'w')

    for step, batch in tqdm(enumerate(loader), desc='eval_steps', total=len(loader)):
        token_strs = [[word for word in sent]
                      for sent in np.asarray(batch[-2]).T]
        sentences = batch[-1]
        token_ids, att_mask = map(lambda x: x.to(args.device), batch[:-2])

        with torch.no_grad():
            """
            pred_logit: (B, L, 3)
            pred_hidden: (B, L, D)
            pred_tags: (B, P, L) ~ list of tensors, where P is # of predicate in each batch
            """

            pred_logit, pred_hidden = model.extract_predicate(
                input_ids=token_ids, attention_mask=att_mask)
            pred_tags = torch.argmax(pred_logit, 2)
            pred_tags = utils.filter_pred_tags(pred_tags, token_strs)
            pred_tags = utils.get_single_predicate_idxs(pred_tags)
            pred_probs = torch.nn.Softmax(2)(pred_logit)

            for cur_pred_tags, cur_pred_hidden, cur_att_mask, cur_token_id, cur_pred_probs, token_str, sentence \
                    in zip(pred_tags, pred_hidden, att_mask, token_ids, pred_probs, token_strs, sentences):
                cur_pred_masks = utils.get_pred_mask(
                    cur_pred_tags).to(args.device)
                n_predicates = cur_pred_masks.shape[0]
                if n_predicates == 0:
                    continue  # if there is no predicate, we cannot extract.
                cur_pred_hidden = torch.cat(
                    n_predicates * [cur_pred_hidden.unsqueeze(0)])
                cur_token_id = torch.cat(
                    n_predicates * [cur_token_id.unsqueeze(0)])

                cur_extractions, cur_extraction_idxs = utils.get_tuple(
                    sentence, cur_pred_tags, tokenizer)
                cur_confidences = utils.get_confidence_score(
                    cur_pred_probs, cur_extraction_idxs)
                for extraction, confidence in zip(cur_extractions, cur_confidences):
                    if args.binary:
                        file.write("\t".join([sentence] +
                                             [str(1.0)] + extraction[:3]) + '\n')
                    else:
                        file.write(
                            "\t".join([sentence] + [str(confidence)] + extraction) + '\n')
