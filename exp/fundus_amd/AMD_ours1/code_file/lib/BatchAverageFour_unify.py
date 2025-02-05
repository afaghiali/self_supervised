import torch
from torch import nn
import numpy as np

def deleteFrom2D(arr2D, row, column):
    'Delete element from 2D numpy array by row and column position'
    arr2D = arr2D.cpu().data.numpy()
    modArr = np.delete(arr2D, row * arr2D.shape[1] + column)
    modArr = torch.from_numpy(modArr).to(device)
    return modArr

class BatchCriterionFour_unify(nn.Module):
    ''' Compute the loss within each batch
    '''

    def __init__(self, negM, T, batchSize, args):
        super(BatchCriterionFour_unify, self).__init__()
        self.negM = negM
        self.T = T
        self.domain = args.domain
        # self.stripe = stripe
        num = 4 if self.domain else 2
        self.diag_mat = 1 - torch.eye(batchSize * num).to(device)

        # clear neg
        index = list(range(0, batchSize * num))
        index_second = [[index[i+1], index[i]] for i in range(0, batchSize * num, 2)]
        index_second = sum(index_second, [])
        self.diag_mat[index, index_second] = 0

    def forward(self, x, targets):
        batchSize = x.size(0)

        # get positive innerproduct
        reordered_x = torch.cat((x.narrow(0, batchSize // 2, batchSize // 2), \
                             x.narrow(0, 0, batchSize // 2)), 0)

        pos = (x * reordered_x.data).sum(1).div_(self.T).exp_()
        # get all innerproduct, remove diag
        all_prob = torch.mm(x, x.t().data).div_(self.T).exp_() * self.diag_mat
        all_div = all_prob.sum(1)

        # cross-domain positive
        idx = list(np.arange(1, int(batchSize), 2))
        idx1 = np.array([item - 1 for item in idx])
        idx = np.array(idx)
        index = np.stack([idx, idx1])
        index = list(index.flatten("F"))
        reordered_x = reordered_x[index, :]

        pos_cross_domain = (x * reordered_x.data).sum(1).div_(self.T).exp_()
        lnPmt_crossdomain = torch.div(pos_cross_domain, all_div)


        lnPmt = torch.div(pos, all_div)
        # negative probability
        Pon_div = all_div.repeat(batchSize, 1)
        lnPon = torch.div(all_prob, Pon_div.t())
        lnPon = -lnPon.add(-1)

        # equation 7 in ref. A (NCE paper)
        lnPon.log_()
        # also remove the pos term

        lnPon = lnPon.sum(1) - (-lnPmt.add(-1)).log_() - (-lnPmt_crossdomain.add(-1)).log_()
        lnPmt.log_()
        lnPmt_crossdomain.log_()

        lnPmtsum = lnPmt.sum(0)
        lnPonsum = lnPon.sum(0)
        lnPmt_crossdomain = lnPmt_crossdomain.sum(0)

        # negative multiply m
        lnPonsum = lnPonsum * self.negM
        loss = - (lnPmtsum + lnPonsum + lnPmt_crossdomain) / batchSize



        return loss
